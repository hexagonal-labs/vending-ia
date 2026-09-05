# Plan final: catálogo, proveedores y pricing mediante MCP

## Objetivo

Construir una solución que compare el coste de los productos de vending frente a uno o varios proveedores, calcule su margen real y genere Excel auditables por proveedor y máquina.

Se admitirán dos orígenes de precio:

- API: se consulta el catálogo actual al ejecutar pricing y se guarda un snapshot.
- Factura PDF/imagen: se adjunta la factura, se extraen y validan sus líneas y se actualiza el catálogo Excel del proveedor.

No se usará base de datos en esta fase. Excel, documentos fuente y un índice JSON serán la persistencia operativa. Los contratos y puertos dejarán preparada una migración posterior a PostgreSQL/Supabase.

## Decisiones de negocio cerradas

### PVP

La única fuente de verdad del precio de venta es MachinePrice de Nayax.

No se usarán CashPrice, CreditCardPrice ni otros precios para el margen. Si falta MachinePrice, el producto se listará con estado SIN_MACHINE_PRICE y sin margen calculado.

### Coste

El coste usado para margen incluye IVA y recargo de equivalencia.

    coste_pack_final =
      coste_pack_neto
      + (coste_pack_neto × IVA)
      + (coste_pack_neto × recargo_equivalencia)

    coste_unitario_final =
      coste_pack_final / unidades_vendibles_por_pack

    margen =
      (MachinePrice - coste_unitario_final) / MachinePrice

IVA y recargo serán parámetros explícitos por proveedor o línea. Nunca se codificarán como constantes invisibles.

### Precio vigente

El precio vigente será el último registro confirmado por momento de importación, ingested_at; no por fecha de emisión de la factura.

Reimportar exactamente la misma factura no creará un precio nuevo. Se deduplicará mediante hash del fichero y número de factura cuando exista.

Una nueva factura solo actualiza los productos que contiene. Si no contiene un producto, su último coste vigente se conserva.

## Arquitectura MCP

nayax-agents-langgraph es el núcleo de conversación y orquestación. No es la fuente de verdad de catálogo, ofertas ni históricos.

    nayax-agents-langgraph
      router + workflows + clientes MCP tipados
             |
      +------+------------------------+--------------------+
      |                               |                    |
      v                               v                    v
    nayax-bridge                supplier-bridge      invoice-bridge
    máquinas y PVP              APIs proveedor       PDFs, imagen y OCR
      |                               |                    |
      +-------------------------------+--------------------+
                                      |
                                      v
                         pricing-catalog-bridge
          Excel, historial, matching, revisiones y reportes

Los servicios no se llamarán entre sí por MCP. Los workflows del agente los orquestan usando puertos de aplicación y adaptadores MCP tipados.

## Servicios

### nayax-bridge

Se mantiene con una sola responsabilidad: Nayax Lynx.

Debe proporcionar machineProductId, machineId, NayaxProductID, ProductName, EAN cuando exista, MachinePrice, selección y stock. No conoce facturas, proveedores, matching ni Excel de comparación.

### supplier-bridge

Integra los proveedores que exponen API, CSV u otro medio directo autorizado.

Cada adaptador interno devuelve el mismo contrato de oferta, aunque su origen sea diferente. El servicio no calcula márgenes ni escribe los Excel locales.

Herramientas iniciales:

    list_suppliers()
    fetch_supplier_offers(supplier_id)
    get_supplier_offer(supplier_id, supplier_sku)

### invoice-bridge

Identifica y extrae facturas adjuntas.

Primero intenta texto/tablas de PDF. Usa OCR o visión solo si no hay texto útil. Devuelve datos estructurados y validaciones; no hace matching ni decide precios vigentes.

Herramientas iniciales:

    inspect_invoice(source_uri)
    extract_invoice(source_uri, supplier_id?)

source_uri es una referencia al fichero ya recibido por el agente. No se envían PDFs codificados en Base64 por MCP.

### pricing-catalog-bridge

Es dueño del estado local y de los artefactos Excel:

- catálogo actual e histórico por proveedor;
- mappings confirmados y aliases;
- normalización y matching determinista;
- pendientes de revisión;
- snapshots API e importaciones de factura;
- reportes proveedor-máquina.

Herramientas iniciales:

    ingest_invoice(extracted_invoice, idempotency_key)
    record_supplier_snapshot(supplier_id, offers, observed_at, idempotency_key)
    match_products(vending_products, supplier_id)
    list_pending_reviews(supplier_id?)
    confirm_match(review_id, canonical_product_id, idempotency_key)
    generate_machine_supplier_report(machine, supplier_id, run_id)

Toda escritura incluye run_id, idempotency_key y respuesta de auditoría.

## Workflows LangGraph

### workflow info

Se mantiene conversacional y de lectura. Puede consultar Nayax y, cuando corresponda, catálogo local para responder preguntas sobre máquinas, productos y precios conocidos.

### workflow pricing

El workflow pricing será determinista. El LLM solo redacta un resumen de resultados ya calculados.

    collect_machine_inventory
      -> refresh_api_supplier_snapshots
      -> load_latest_invoice_supplier_prices
      -> normalize_and_match
      -> calculate_margins
      -> generate_excel_reports
      -> redact_summary

La consulta de productos de máquinas tendrá concurrencia limitada para no multiplicar llamadas de detalle a Nayax.

### workflow supplier_ingestion

Nuevo flujo para facturas y catálogos externos:

    receive_source
      -> inspect_supplier
      -> extract_invoice_or_fetch_catalog
      -> validate_lines
      -> ingest_catalog_history
      -> create_review_items

Solo será un grafo de LangGraph si tiene que pausarse para revisión humana. La extracción, normalización y validación vivirán en servicios Python deterministas.

## Contratos de dominio

El dominio usará dataclasses inmutables y Decimal para importes. Pydantic validará datos en límites MCP, APIs, CSV y facturas.

### Producto de máquina

    canonical_product_id = nayax:{NayaxProductID}
    machine_id
    machine_product_id
    selection_code
    product_name              # ProductName
    ean
    machine_price             # MachinePrice

ProductName es el nombre de referencia. DEXProductName solo es fallback cuando no exista nombre real.

### Oferta de proveedor

    supplier_id
    supplier_sku
    supplier_reference
    barcode
    raw_name
    availability
    currency
    price_scope               # unit | pack | case | unknown
    pack_expression_raw
    purchase_quantity
    units_per_priced_pack
    content_value
    content_unit              # ml | l | g | kg | unit
    pack_price_net
    unit_price_net
    discount_pct
    vat_rate
    equivalence_surcharge_rate
    observed_at
    source_reference

### Resultado de matching

    canonical_product_id
    supplier_product_key
    status                    # MATCHED_EXACT | MATCHED_CONFIRMED |
                              # PENDING_REVIEW | UNMATCHED |
                              # SOURCE_INCOMPLETE
    method                    # ean | sku | confirmed_mapping |
                              # normalized_attributes | fuzzy
    confidence
    alternatives
    reason

Un precio sin match seguro no se utiliza para margen. Se muestra en Excel y queda disponible para revisión.

## Facturas y parsers de proveedor

### Detección de proveedor

invoice-bridge identifica el emisor por orden de fiabilidad:

1. CIF/NIF del emisor.
2. Razón social normalizada.
3. Dirección, teléfono, dominio o serie de factura.
4. Encabezados y geometría de la tabla.
5. Logo como señal auxiliar.

Si la confianza no es suficiente, la factura queda como PROVEEDOR_PENDIENTE. El usuario confirma o crea el proveedor una vez y esa regla se reutiliza.

### Parser Cashoreca

Cashoreca tendrá un perfil y parser específico para:

    REFERENCIA | COD. BARRA | ARTÍCULO | CANTID | PRE/U | DTO% | IMPORTE | IVA

Interpretación:

- CANTID: número de packs/cajas comprados.
- PRE/U: precio neto del pack/caja antes de descuento, cuando aplique.
- DTO%: descuento de la línea.
- IMPORTE: total neto de la línea después del descuento.
- IVA: tipo impositivo.
- Expresiones como 1*24: un pack contiene 24 unidades vendibles.

La fuente de verdad del coste neto por pack será:

    coste_pack_neto = IMPORTE / CANTID

Se validará:

    CANTID × PRE/U × (1 - DTO%) ≈ IMPORTE

dentro de una tolerancia de redondeo monetario. Si no cuadra, la línea no actualiza el precio vigente y se crea una revisión.

### Nuevos proveedores

La estructura permite añadir proveedores sin modificar pricing:

    invoice-bridge/
    ├── profiles/
    │   ├── cashoreca.yaml
    │   ├── proveedor_x.yaml
    │   └── generic.yaml
    ├── parsers/
    │   ├── cashoreca.py
    │   ├── table_invoice.py
    │   └── generic_extractor.py
    └── normalizers/
        ├── package_parser.py
        └── product_attributes.py

Cada perfil declara columnas, cantidades, unidades, descuentos y si el precio es unitario, por pack o por caja.

El parser genérico puede proponer extracciones, pero no actualiza precios si no conoce el alcance del precio ni las unidades por pack.

### Packs y unidades

El normalizador detectará:

- volumen: ml, cl, l;
- peso: g, kg;
- unidades: ud, u, unidades;
- formato: lata, botella, brick, bolsa y pack;
- embalaje: 1*24, 2x12, 6 x 4.

    330 ML  -> 330 ml
    0,33 L  -> 330 ml
    50 CL   -> 500 ml
    1*24    -> 24 unidades vendibles por pack

No se asumirá que cualquier 6x4 equivale a 24 unidades. Si el perfil no confirma su semántica, se asigna estado PACK_OR_UNIT_UNKNOWN.

## Matching

La identidad canónica inicial es NayaxProductID. Referencias y códigos de barras de proveedor se guardan como evidencia, pero no son dependencia única ni identidad canónica.

Orden de matching:

1. EAN/GTIN validado y confirmado.
2. SKU o referencia del mismo proveedor con mapping confirmado.
3. Alias manual confirmado.
4. Marca, variante, formato y peso/volumen normalizados.
5. RapidFuzz para proponer alternativas.

Diferencias de tamaño, sabor, versión, formato o pack relevante penalizan el resultado y no se compensan solo porque el texto sea parecido.

Umbrales iniciales:

    >= 0.95   match automático
    0.75-0.94 revisión
    < 0.75    no match

El LLM no participa en la primera versión del matching. En el futuro podrá proponer una decisión para casos ambiguos, pero no persistirá asociaciones sin confirmación humana.

## Persistencia local

pricing-catalog-bridge será dueño de los ficheros:

    pricing-data/
    ├── providers/
    │   ├── cashoreca/
    │   │   ├── catalog.xlsx
    │   │   ├── invoices/
    │   │   └── source/
    │   └── distribuidora-mayorista/
    │       ├── catalog.xlsx
    │       ├── snapshots/
    │       └── source/
    ├── catalog/
    │   └── product-mappings.xlsx
    ├── runs/
    │   └── {run_id}/reports/
    └── index.json

Cada catalog.xlsx de proveedor contiene:

- Ofertas actuales: última oferta confirmada por producto de proveedor.
- Historial precios: append-only, una fila por factura o snapshot API.
- Importaciones: hash, fuente, fecha de factura, ingested_at y resultado.
- Sin match: ofertas sin producto Nayax confirmado.
- Pendientes revisión: casos ambiguos, packs y datos incompletos.
- Parámetros: IVA, recargo, moneda y reglas locales.

product-mappings.xlsx contiene el producto Nayax canónico, proveedor, SKU, EAN/alias, método de confirmación y fecha. Sustituye progresivamente el YAML actual basado en nombres exactos.

Las facturas originales no se sobrescriben. Las escrituras de Excel se harán con bloqueo, fichero temporal y reemplazo atómico.

## Excel de comparación

Por cada ejecución se genera un Excel por combinación proveedor-máquina:

    runs/{run_id}/reports/{supplier_id}/{machine_id}.xlsx

Pestañas:

- Resumen: márgenes bajos, variaciones de coste, no matches y totales.
- Comparación: todos los productos de la máquina, incluidos no matches.
- Sin match: motivo, datos fuente y candidatos.
- Parámetros: IVA, recargo y márgenes objetivo.
- Origen: facturas/snapshots, fechas, hashes y run_id.

Columnas principales:

    Máquina | Selección | NayaxProductID | ProductName | EAN | MachinePrice
    Proveedor | SKU | Nombre proveedor | Estado match | Método | Confianza
    Unidades pack | Coste neto pack | IVA | Recargo | Coste final pack
    Coste unitario final | Margen | PVP 40% | PVP 50% | PVP 60%
    Coste anterior | Variación € | Variación % | Origen

Los cálculos se verifican en Python y se expresan también mediante fórmulas auditables en Excel. Las cifras y fechas se escriben como valores tipados, no como texto.

Además se genera un resumen consolidado por máquina que compara proveedores y señala el menor coste comparable.

## Alertas y revisión

Alertas iniciales:

    MARGIN_BELOW_TARGET
    SUPPLIER_PRICE_INCREASE
    SUPPLIER_PRICE_DECREASE
    NEW_CHEAPER_SUPPLIER
    UNMATCHED_PRODUCT
    AMBIGUOUS_PRODUCT_MATCH
    PACK_OR_UNIT_UNKNOWN
    SIN_MACHINE_PRICE

Una revisión permite confirmar candidato, elegir otro producto Nayax, crear alias, marcar producto no ofertado o corregir unidades por pack.

Una revisión no confirmada no modifica el coste vigente ni el margen.

## Fases de implementación

### Fase 1: contratos y preparación

- Definir contratos JSON/MCP versionados.
- Cambiar LangGraph para consumir prices.machine.
- Introducir Decimal para importes.
- Crear fixtures saneadas de Nayax, proveedor API y facturas Cashoreca.
- Limitar concurrencia de consulta de máquinas.

Criterio: pricing lista MachinePrice por producto sin depender de CashPrice.

### Fase 2: pricing-catalog-bridge y Excel

- Crear el proyecto MCP y puertos de aplicación.
- Implementar directorios, índice de hashes y bloqueo.
- Crear plantillas de catálogo, mappings y reportes.
- Implementar importación append-only e idempotente.

Criterio: una oferta estructurada actualiza catálogo actual e historial sin duplicados.

### Fase 3: normalización y matching

- Añadir RapidFuzz y normalizador de producto, unidad y pack.
- Implementar EAN, SKU, mapping confirmado, atributos y fuzzy.
- Migrar el YAML actual solo en modo informe; no convertir ambigüedades.
- Crear pendientes de revisión.

Criterio: productos equivalentes se relacionan con explicación y los tamaños o variantes distintos no se autoasocian.

### Fase 4: proveedor API

- Extraer DistribuidoraMayoristaClient a supplier-bridge.
- Normalizar sus ofertas al contrato común.
- Crear snapshots fechados e importarlos al catálogo Excel.
- Configurar explícitamente si el precio API incluye IVA y recargo.

Criterio: cada pricing guarda snapshot y calcula variación frente al anterior.

### Fase 5: facturas y Cashoreca

- Crear invoice-bridge con PDF/texto, OCR fallback y validación Pydantic.
- Implementar identificación de proveedor y parser Cashoreca.
- Implementar packs, volumen/peso, descuentos y validación matemática.
- Importar líneas validadas al catálogo local.

Criterio: una factura Cashoreca genera histórico y coste unitario final, sin inventar datos incompletos.

### Fase 6: parser genérico y nuevos proveedores

- Añadir perfiles configurables y parser genérico de tablas.
- Crear confirmación de proveedor desconocido.
- Crear reglas reutilizables de detección y errores.

Criterio: una factura no soportada se clasifica y queda en revisión si no hay certeza suficiente.

### Fase 7: evolucionar workflow pricing

- Conectar Nayax, proveedor API, catálogo de facturas y matcher por MCP.
- Calcular solo con MachinePrice y coste final unitario.
- Generar Excel proveedor-máquina y consolidado por máquina.
- Mantener todos los productos aunque no hagan match.

Criterio: una ejecución produce reportes trazables de cada proveedor y máquina.

### Fase 8: revisión, alertas y modo sombra

- Añadir herramientas para resolver pendientes.
- Activar alertas de margen, subidas/bajadas y proveedor más barato.
- Ejecutar matcher nuevo junto al YAML actual antes de retirar este último.

Criterio: matches confirmados se reutilizan y no hay asociaciones automáticas de baja confianza.

### Fase 9: evaluación y endurecimiento

- Construir dataset real anonimizado.
- Medir falsos positivos, falsos negativos y cobertura.
- Calibrar umbrales, reglas y aliases.
- Añadir pruebas MCP, integración y extremo a extremo.
- Añadir observabilidad y documentación operativa.

Criterio: un cambio de parser o matcher no degrada el dataset sin decisión explícita.

## Fuera de alcance inicial

- Base de datos PostgreSQL/Supabase.
- Actualización automática de precios en Nayax.
- Decisiones automáticas de compra.
- LLM como mecanismo principal de matching.
- OCR sin validación matemática o humana.

## Definición de MVP terminado

1. Se puede adjuntar una factura Cashoreca y extraer sus líneas con packs, IVA y precio.
2. Se conserva factura, histórico y coste vigente en el Excel del proveedor.
3. Se consulta un proveedor API y se guarda su snapshot actual.
4. Se leen posiciones de máquina desde Nayax usando MachinePrice.
5. Se hacen matches seguros entre productos de máquina y proveedor.
6. Se muestran productos sin match o con datos incompletos.
7. Se genera un Excel por proveedor-máquina y un consolidado por máquina.
8. Se calcula margen con IVA y recargo.
9. Se informa qué costes subieron, bajaron o requieren revisión.

