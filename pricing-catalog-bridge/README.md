# pricing-catalog-bridge

Servicio MCP independiente que conserva el catálogo local de precios de proveedores.

Es dueño de `pricing-data/`: el índice JSON, los documentos de origen y los Excel
de catálogo. No consulta Nayax ni proveedores externos y no calcula márgenes.

## Alcance actual

- inicializa las plantillas Excel de catálogo, mappings y reporte;
- registra snapshots estructurados de proveedores de forma append-only;
- deduplica por `idempotencyKey` y por hash de contenido;
- reconstruye el Excel del proveedor desde el índice para mantenerlo auditable;
- protege las escrituras con bloqueo de proceso y reemplazo atómico.
- normaliza producto, tamaño y formato antes de hacer matching;
- confirma por EAN o mapping previamente confirmado y deja los casos fuzzy en revisión.

`match_products` requiere `runId` e `idempotencyKey`. Un tamaño, formato o
variante contradictoria no se asocia automáticamente.

## Ejecutar

```bash
python -m pricing_catalog_bridge.interfaces.mcp_server
```

`PRICING_DATA_DIR` permite cambiar la ubicación de los datos. Por defecto es
`./pricing-data` desde el directorio de ejecución.
