# supplier-bridge

Servicio MCP independiente para proveedores con catálogo directo o API.

Actualmente integra Distribuidora Mayorista y devuelve snapshots en el contrato
`supplier-offer-snapshot/v1`. No consulta Nayax, no hace matching y no escribe
los Excel: el workflow central deberá enviar el `snapshot` resultante a
`pricing-catalog-bridge` en la fase 7.

El coste final de cada oferta se calcula con una política explícita de IVA y
recargo de equivalencia. Antes de usar datos reales, configura si la API ya
incluye cada componente en `.env`; no se asume implícitamente.

## Herramientas MCP

- `list_suppliers`
- `fetch_supplier_offers`
- `get_supplier_offer`

## Ejecutar

```bash
python -m supplier_bridge.interfaces.mcp_server
```
