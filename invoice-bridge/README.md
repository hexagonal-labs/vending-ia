# invoice-bridge

MCP de extracción de facturas. Identifica al proveedor antes de extraer y no
inventa precios cuando el texto, el pack o la columna de importe no son fiables.
Actualmente incluye Cashoreca y devuelve revisión pendiente cuando una línea no
se puede validar con seguridad.

## Estrategia de extracción

Los PDF digitales con líneas Cashoreca completamente verificadas se procesan de
forma determinista. Las fotos y los PDF escaneados se procesan exclusivamente
con el proveedor de visión. Si el proveedor no responde, rechaza el documento o
devuelve un JSON que no cumple el contrato, la extracción falla con el motivo;
nunca se sustituyen los datos por un OCR local parcial.

```env
INVOICE_VISION_PROVIDER=openclaw_gateway
INVOICE_VISION_MODEL=openclaw/nayax-invoice-vision
INVOICE_VISION_TIMEOUT_SECONDS=120
INVOICE_VISION_MAX_ATTEMPTS=2
```

Con OpenClaw, `INVOICE_VISION_MODEL` debe apuntar a un agente dedicado con
visión; no debe usar el agente puente de tools Nayax. El bridge envía imágenes
y PDF por OpenResponses y exige JSON validado por el contrato
`supplier-invoice-ingestion/v1`. Si el proveedor devuelve JSON inválido, hace
un único reintento y después devuelve el error al cliente; las líneas
incompletas siempre quedan en `REVIEW_REQUIRED`.

Para producción se conserva el mismo contrato cambiando únicamente:

```env
INVOICE_VISION_PROVIDER=openai
OPENAI_API_KEY=...
INVOICE_VISION_MODEL=gpt-5-mini
```
