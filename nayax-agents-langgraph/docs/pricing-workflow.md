# Workflow de pricing con bridges MCP

El agente LangGraph es el único orquestador. Los servicios hermanos conservan
responsabilidades aisladas y se comunican con el núcleo por MCP/STDIO:

```text
LangGraph (orquestador)
 ├─ nayax-bridge             → máquinas, MachinePrice y ProductName
 ├─ supplier-bridge          → ofertas actuales de proveedores con API
 ├─ invoice-bridge           → identificación y extracción conservadora de facturas
 └─ pricing-catalog-bridge   → catálogo, historial, matching, revisiones y XLSX
```

## Reglas aplicadas

- El PVP es siempre `MachinePrice` de Nayax; efectivo/tarjeta no intervienen.
- El coste del catálogo incluye IVA y recargo de equivalencia.
- En facturas, el precio actual es el de la última factura adjuntada. Las
  facturas antiguas se conservan en historial y un precio menor posterior
  también pasa a ser el vigente.
- Referencia y EAN sirven como evidencia de matching, no como identidad
  canónica. La identidad de máquina es `nayax:{NayaxProductID}`.
- Una línea de factura sin unidades por pack, con importes inconsistentes o
  extracción incierta queda en revisión y no actualiza el coste.

## Facturas

`invoice-bridge` acepta texto UTF-8 y PDF con texto seleccionable. Un PDF
escaneado sin texto no se inventa: devuelve `REVIEW_REQUIRED` para poder
revisarlo o añadir un perfil/OCR específico. Cashoreca reconoce líneas en el
formato:

```text
REFERENCIA | COD. BARRA | ARTÍCULO | CANTID | PRE/U | DTO% | IMPORTE | IVA
```

Por ejemplo, `1*24` significa 24 unidades por pack. El coste por unidad se
calcula con `IMPORTE / CANTID`, más IVA y recargo, dividido entre 24.

Para cargar una factura desde un cliente MCP:

1. Llamar `invoice.extract_invoice(source_uri)`.
2. Revisar `status` y cada `validationStatus`.
3. Llamar `pricing_catalog.record_supplier_invoice(invoice, idempotency_key, equivalence_surcharge_rate)`.

El hash del fichero, el número de factura si existe y la clave de idempotencia
impiden duplicados.

## Comparador

El comando `nayax-pricing-report` acepta dos fuentes de proveedor:

- `--source api`: actualiza el catálogo con `supplier-bridge` antes de comparar.
- `--source catalog`: usa el coste vigente que ya está importado desde facturas.

Por ejemplo, para CASHORECA:

```bash
uv run nayax-pricing-report --provider cashoreca --source catalog
```

En LangGraph Studio, el input equivalente es:

```json
{"supplier_id":"cashoreca","provider_source":"catalog"}
```

Sin `supplier_id`, el grafo compara automáticamente todos los proveedores que
tengan productos vigentes en el catálogo local:

```json
{"provider_source":"catalog"}
```

La fuente `api` requiere un proveedor explícito, porque no todos los
proveedores disponen de integración API.

Después el comando:

1. Actualiza el snapshot API o usa el catálogo de facturas, según su fuente.
2. Obtiene `ProductName` y `MachinePrice` de todas las máquinas Nayax.
3. Ejecuta matching con EAN, atributos normalizados y fuzzy conservador.
4. Genera un XLSX por máquina y proveedor en `reports/...`.

Los informes nuevos se nombran como
`proveedor-nombre-maquina-DD_MM_YYYY_HH:MM.xlsx`, con hora local de Madrid.

Cada libro incluye `Comparación`, `Sin match`, `Resumen` y `Parámetros`. Los
productos sin match, sin NayaxProductID o sin `MachinePrice` se incluyen y no
producen un margen ficticio. Los candidatos ambiguos se consultan con
`pricing_catalog.list_pending_reviews` y se confirman únicamente con
`confirm_product_match`.

## Desarrollo y Docker

Los cuatro repositorios deben ser carpetas hermanas:

```text
workspace/
├── nayax-agents-langgraph/
├── nayax-bridge/
├── supplier-bridge/
├── invoice-bridge/
└── pricing-catalog-bridge/
```

Para desarrollo local, instala las dependencias de cada bridge (el orquestador
detecta automáticamente su `.venv` cuando existe) y ejecuta el comando desde
`nayax-agents-langgraph`:

```bash
uv run nayax-pricing-report
```

Docker usa esos repositorios como contextos de build. Tras cambiar código en
cualquiera de ellos, desde `nayax-agents-langgraph` ejecuta:

```bash
docker compose --env-file .env.docker up -d --build
docker compose --env-file .env.docker logs -f nayax-agents
```
