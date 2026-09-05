# nayax-bridge

API puente sobre Nayax Lynx para operar máquinas de vending. Un único núcleo de negocio,
consumible por **HTTP** (aplicación frontal) y por **MCP** (agentes de IA).

## Arranque rápido

```bash
npm install
cp .env.example .env      # rellena NAYAX_TOKEN como mínimo
npm test                  # 18 tests, sin red
npm run dev               # HTTP en http://localhost:3000
```

Comprobación:

```bash
curl http://localhost:3000/health
```

## Configuración mínima

| Variable | Para qué |
|---|---|
| `NAYAX_BASE_URL` | `https://qa-lynx.nayax.com` (QA) o `https://lynx.nayax.com` (producción) |
| `NAYAX_TOKEN` | Tu Bearer de Lynx. Se obtiene en Nayax Core → Security & Token |
| `NAYAX_OPERATOR_ID` | Tu id de operador, necesario para los widgets de ventas |
| `API_KEYS` | Credenciales de *esta* API: `clave:rol` separadas por comas |
| `WRITES_ENABLED` | `false` deja todo en solo lectura |
| `MAX_PRICE_CHANGE_RATIO` | Variación máxima de precio sin confirmación (0.30 = 30%) |

Roles: `viewer` (solo lectura), `operator` (humano con escritura), `agent` (IA con escritura).

## API HTTP

Todas las rutas bajo `/api/v1` requieren cabecera `x-api-key`.

| Método | Ruta | Rol mínimo |
|---|---|---|
| `GET` | `/health` | — |
| `GET` | `/api/v1/machines` | viewer |
| `GET` | `/api/v1/machines/:machineId/products` | viewer |
| `GET` | `/api/v1/sales/summary?from=&to=&machineId=` | viewer |
| `GET` | `/api/v1/sales/by-machine?from=&to=` | viewer |
| `PUT` | `/api/v1/machines/:machineId/products/:machineProductId/prices` | operator |
| `POST` | `/api/v1/prices/bulk` | operator |
| `GET` | `/api/v1/audit` | operator |

### Ejemplo: simular un cambio de precio

```bash
curl -X PUT http://localhost:3000/api/v1/machines/5001/products/101/prices \
  -H "x-api-key: dev-operator-key" \
  -H "Content-Type: application/json" \
  -d '{"prices": {"card": 1.80}, "dryRun": true}'
```

`dryRun` es **`true` por defecto**. Para aplicar de verdad hay que enviar `"dryRun": false`
explícitamente. Es fricción buscada: al otro lado hay máquinas cobrando dinero real.

## Servidor MCP

```bash
npm run dev:mcp
```

Para conectarlo a Claude Code una vez compilado:

```bash
npm run build
claude mcp add --transport stdio nayax-bridge -- node /ruta/absoluta/al/proyecto/dist/mcp.js
```

Herramientas expuestas:

**Lectura:** `list_machines`, `list_machine_products`, `get_sales_summary`,
`get_sales_by_machine`, `get_price_change_history`

**Escritura:** `update_product_price`, `bulk_update_prices` — ambas simulan por defecto.

El flujo que el agente tiene instruido seguir: localizar la máquina → obtener el
`machineProductId` → simular → mostrar al usuario → aplicar solo tras confirmación.

## Tests

```bash
npm test
```

Los tests unitarios no tocan la red: los puertos se sustituyen por dobles. Si un test
necesita internet, no es unitario.

## Arquitectura

Ver `CLAUDE.md` para las reglas de capas, convenciones y el estado de lo que falta.
