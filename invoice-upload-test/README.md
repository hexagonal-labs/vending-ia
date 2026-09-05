# invoice-upload-test

Interfaz temporal para probar la carga de facturas sin construir todavía la
pantalla definitiva de la aplicación principal.

La aplicación no interpreta facturas ni escribe Excel por su cuenta. Sólo usa
una zona temporal durante la petición y utiliza MCP para:

1. llamar a `invoice-bridge.archive_invoice` y `invoice-bridge.extract_invoice`;
2. mostrar el resultado y las líneas que requieren revisión;
3. cuando se confirma, llamar a `pricing-catalog-bridge.record_supplier_invoice`.

## Arranque

Los tres proyectos deben ser carpetas hermanas. Desde esta carpeta:

```bash
python -m venv .venv
.venv/bin/pip install -e . -e ../invoice-bridge -e ../pricing-catalog-bridge
.venv/bin/invoice-upload-test
```

Abre <http://127.0.0.1:8088>. La interfaz no conserva datos duraderos:
`invoice-bridge` archiva los originales y `pricing-catalog-bridge` conserva
el catálogo y el historial de costes en sus propios volúmenes Docker.

## Variables opcionales

```env
INVOICE_BRIDGE_DIR=../invoice-bridge
PRICING_CATALOG_BRIDGE_DIR=../pricing-catalog-bridge
PRICING_DATA_DIR=/var/lib/pricing-catalog-bridge
INVOICE_DATA_DIR=/var/lib/invoice-bridge
INVOICE_UPLOAD_STAGING_DIR=/tmp/invoice-upload-test
INVOICE_EQUIVALENCE_SURCHARGE_RATE=0.052
INVOICE_UPLOAD_MAX_BYTES=20971520
INVOICE_TESSERACT_ENABLED=true
INVOICE_TESSERACT_LANGUAGES=spa+eng
INVOICE_VISION_PROVIDER=openclaw_gateway
```

El botón **Confirmar e importar** sólo transmite las líneas `VALID`; las que
indican `REVIEW_REQUIRED` nunca modifican el coste actual.

Para fotos y PDF escaneados, `invoice-bridge` intenta primero **Tesseract
local** (español e inglés) y aplica el parser determinista de Cashoreca. Si no
puede identificar o validar la factura, usa como respaldo
`OPENCLAW_GATEWAY_URL`, `OPENCLAW_GATEWAY_TOKEN` y
`OPENCLAW_GATEWAY_MODEL` del proyecto hermano `nayax-agents-langgraph`.
Envía el documento al endpoint OpenResponses y vuelve a validar
determinísticamente cantidad, PRE/U, descuento, importe, IVA y unidades por
pack antes de que la interfaz permita importar.

## Arranque con Docker

Desde esta carpeta, con `invoice-bridge` y `pricing-catalog-bridge` como
carpetas hermanas:

```bash
docker volume create invoice-bridge-data
docker volume create pricing-catalog-data
docker compose up -d --build
docker compose logs -f invoice-upload-test
```

Abre <http://127.0.0.1:8088>. Los volúmenes `invoice-bridge-data` y
`pricing-catalog-data` persisten, respectivamente, los originales y el
catálogo. La interfaz puede recrearse o eliminarse sin borrar esos datos.
Los volúmenes son externos: no se eliminan tampoco con `docker compose down -v`
desde este proyecto temporal.

Antes del arranque Docker crea `.env` a partir de `.env.example`:

```bash
cp .env.example .env
```

Para detenerlo:

```bash
docker compose down
```
