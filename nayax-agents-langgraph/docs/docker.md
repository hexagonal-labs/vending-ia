# Docker: agente y bridges de pricing

Esta configuración crea una imagen conjunta con Python, Node.js, LangGraph y
`nayax-bridge` y los bridges de proveedor, factura y catálogo. El agente los
ejecuta mediante MCP por STDIO.

Los repositorios siguen siendo independientes, pero deben clonarse como
carpetas hermanas:

```text
workspace/
├── nayax-agents-langgraph/
├── nayax-bridge/
├── supplier-bridge/
├── invoice-bridge/
└── pricing-catalog-bridge/
```

## Requisitos del equipo

En el Mac nuevo solo es necesario instalar:

- Git para clonar los repositorios.
- Docker Desktop u OrbStack.
- SSH/Tailscale si se utiliza el OpenClaw del Mac antiguo.

No es necesario instalar Python, `uv`, Node.js ni las librerías del proyecto
en el Mac nuevo.

## Primer arranque en un Mac nuevo

Clonar ambos repositorios en la misma carpeta padre:

```bash
mkdir -p ~/workspace
cd ~/workspace
git clone https://github.com/hexagonal-labs/nayax-agents-langgraph.git
git clone https://github.com/hexagonal-labs/nayax-bridge.git
# Clona también supplier-bridge, invoice-bridge y pricing-catalog-bridge.
cd nayax-agents-langgraph
```

Crear el fichero local de configuración:

```bash
cp .env.docker.example .env.docker
```

Editar `.env.docker` y completar como mínimo:

- `NAYAX_TOKEN`.
- `API_KEYS`.
- `OPENCLAW_GATEWAY_TOKEN`, si se utiliza OpenClaw remoto.

El fichero `.env.docker` está excluido de Git y no debe subirse al repositorio.

## Usar OpenClaw en el Mac antiguo

Primero abrir el túnel SSH en una terminal del Mac nuevo:

```bash
ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=3 \
  -N -L 18789:127.0.0.1:18789 usuario@mac-antiguo
```

La variable correspondiente en `.env.docker` debe ser:

```env
NAYAX_LLM_PROVIDER=openclaw_gateway
OPENCLAW_GATEWAY_URL=http://host.docker.internal:18789/v1
```

Dentro del contenedor, `127.0.0.1` sería el propio contenedor. Por eso se usa
`host.docker.internal` para llegar al túnel abierto en el Mac nuevo.

## Construir y arrancar

Desde `nayax-agents-langgraph`:

```bash
docker volume create pricing-catalog-data
docker volume create invoice-bridge-data
docker compose --env-file .env.docker build
docker compose --env-file .env.docker up -d
```

Comprobar el estado:

```bash
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f
```

LangGraph quedará disponible en:

```text
http://127.0.0.1:2024
```

Para detenerlo:

```bash
docker compose --env-file .env.docker down
```

Los checkpoints se guardan en el volumen Docker `langgraph-data`. El catálogo
de proveedores usa el volumen externo `pricing-catalog-data` y los originales
de factura el volumen externo `invoice-bridge-data`; ambos sobreviven al
reinicio del contenedor y se comparten con `invoice-upload-test`.

Los Excel visibles para el equipo se exportan automáticamente al propio proyecto:

```text
reports/catalogos/<proveedor>/catalog.xlsx
reports/comparaciones/<proveedor>/<informe-por-máquina>.xlsx
```

Son copias de solo salida del catálogo persistente del bridge. Se actualizan
después de importar una factura, registrar un catálogo desde la API de un
proveedor o generar una comparación de pricing. Estas salidas locales están
excluidas de Git.

## Carga de facturas por LangGraph

Studio muestra el grafo `invoice` y permite probar la revisión por thread. El
input tiene dos alternativas excluyentes:

- `source_uri`: ruta que ya exista dentro del contenedor, por ejemplo un
  original en `/var/lib/invoice-bridge/uploads/...`.
- `filename` y `content_base64`: un frontend o canal de chat codifica el PDF o
  imagen en Base64 y lo envía al grafo. Es la vía destinada a los empleados;
  no expone rutas de sus ordenadores y acepta PDF, JPG, PNG o WEBP de hasta
  20 MB.

El flujo archiva el original, ejecuta la visión IA y se pausa si alguna línea
necesita revisión. El cliente debe reanudar el mismo `thread_id` con:

```json
{
  "action": "apply",
  "corrections": [
    {"lineIndex": 0, "unitsPerPack": "1", "packExpression": "1*1"}
  ]
}
```

Cuando todas las líneas son válidas, se produce una segunda pausa. Reanudarla
con `{"approved": true}` importa la factura al catálogo; con cualquier otro
valor se cancela sin borrar el original. La clave de idempotencia se deriva del
hash del documento, por lo que confirmar dos veces el mismo archivo no duplica
las ofertas.

LangGraph Studio sirve para desarrollar y validar el flujo, pero no es el
canal de adjuntos de los empleados. El chat/web/WhatsApp que se añada después
debe subir el binario y llamar al grafo con `filename` y `content_base64`; las
pausas de revisión se pueden mostrar como formulario conversacional y traducir
a la estructura anterior.

## Visión de facturas con OpenClaw

La extracción de facturas usa un agente distinto del LLM principal:

```env
OPENCLAW_GATEWAY_MODEL=openclaw/nayax-langgraph-bridge
INVOICE_VISION_MODEL=openclaw/nayax-invoice-vision
```

`nayax-langgraph-bridge` conserva las consultas y tools Nayax. El agente
`nayax-invoice-vision` recibe PDF e imágenes, devuelve JSON de factura y no
tiene permisos de escritura ni tools Nayax. Las fotos y PDF escaneados se
extraen exclusivamente con visión IA: si el Gateway falla, la carga comunica el
motivo y no genera un resultado de fallback.

## Cambiar a API de OpenAI

En `.env.docker`, cambiar el proveedor:

```env
NAYAX_LLM_PROVIDER=openai
OPENAI_API_KEY=tu-api-key
NAYAX_LLM_MODEL=gpt-5.4-mini
```

Después recrear el contenedor:

```bash
docker compose --env-file .env.docker up -d --force-recreate
```

En este modo no hace falta el túnel SSH ni tener OpenClaw encendido.

## Desarrollo con el mock de Nayax

La imagen usa por defecto QA de Nayax. Para usar el mock, cambiar en
`.env.docker`:

```env
NAYAX_BASE_URL=http://host.docker.internal:8790
NAYAX_API_PREFIX=/operational/v1
```

El mock debe estar escuchando en el Mac anfitrión y aceptar conexiones fuera
de `127.0.0.1`, si su configuración lo requiere.

## Actualizar el proyecto

Después de descargar cambios:

```bash
git pull
cd ../nayax-bridge && git pull
cd ../nayax-agents-langgraph
docker compose --env-file .env.docker up -d --build
```

## Despliegue en un VPS

Para una primera instalación en un VPS con ambos repositorios:

```bash
git clone https://github.com/hexagonal-labs/nayax-agents-langgraph.git
git clone https://github.com/hexagonal-labs/nayax-bridge.git
cd nayax-agents-langgraph
cp .env.docker.example .env.docker
```

En el VPS se recomienda usar `NAYAX_LLM_PROVIDER=openai` y gestionar los
secretos fuera del repositorio. El modo OpenClaw remoto solo debe usarse si el
VPS tiene conectividad privada y controlada hacia el Mac antiguo.

Antes de publicar el servicio, añadir un reverse proxy HTTPS, firewall y un
volumen persistente para `langgraph-data`.

## Nota sobre la separación futura

La imagen conjunta evita cambios en el código actual porque el agente arranca
`/opt/nayax-bridge/dist/mcp.js` como proceso hijo Node. Separar LangGraph y
`nayax-bridge` en contenedores distintos requerirá cambiar la conexión MCP de
STDIO a un transporte remoto y definir una red interna entre servicios.
