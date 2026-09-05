# Plantilla de contexto para un proyecto de agentes con LangGraph

> Copia este fichero a la raíz de un proyecto nuevo y sustituye los valores
> entre corchetes. Está basado en `nayax-agents-langgraph`, pero no depende de
> Nayax ni de una lógica de negocio concreta.

## 1. Identidad del proyecto

- Nombre: `[PROJECT_NAME]`
- Dominio: `[BUSINESS_DOMAIN]`
- Objetivo: `[DESCRIBE_THE_AGENT_SYSTEM]`
- Python: `3.11+`
- Orquestador: LangGraph
- Proveedor local: OpenClaw OAuth mediante Gateway
- Proveedor de preproducción/producción: OpenAI API mediante `OPENAI_API_KEY`
- Integraciones externas: MCP y `[OTHER_INTEGRATIONS]`

El proyecto debe ser independiente de cualquier proyecto anterior. La lógica
de negocio se reutiliza conceptualmente, pero no se copian dependencias
innecesarias ni se modifica el proyecto original.

## 2. Arquitectura objetivo

La responsabilidad principal pertenece a LangGraph:

```text
Usuario / CLI / Telegram / HTTP
              |
              v
          LangGraph
       /      |       \
   estado   reglas    ToolNode
                       |
                       v
                    MCP/tools
                       |
                       v
              sistemas del dominio
```

El modelo solo interpreta la intención, decide cuándo necesita información y
redacta la respuesta. No debe ejecutar directamente las tools ni contener
reglas de negocio críticas.

Responsabilidades:

- LangGraph: estado, nodos, decisiones de flujo, memoria, reintentos y
  ejecución de tools.
- Dominio: entidades, validaciones, cálculos y reglas deterministas.
- MCP/adaptadores: acceso a APIs, bases de datos y sistemas externos.
- LLM: interpretación, selección de tools y redacción.
- Interfaces: CLI inicialmente; Telegram, HTTP u otras como adaptadores
  independientes.

## 3. Proveedores de LLM

El proveedor se selecciona mediante:

```env
NAYAX_LLM_PROVIDER=openclaw_gateway
```

En un proyecto genérico se recomienda renombrar la variable a:

```env
[PROJECT]_LLM_PROVIDER=openclaw_gateway
```

Los valores esperados son:

- `openclaw_gateway`: desarrollo local con OAuth de OpenClaw.
- `openai`: preproducción y producción con API key.

El cambio de proveedor no debe cambiar los grafos, las tools ni la lógica de
negocio.

### 3.1 Desarrollo local con OpenClaw OAuth

OpenClaw funciona como proveedor de inteligencia. El Gateway recibe el prompt
y devuelve una decisión de tool o una respuesta final.

```text
LangGraph -> OpenClaw Gateway -> decisión JSON
LangGraph -> ToolNode -> MCP/tool real
LangGraph -> OpenClaw Gateway -> respuesta final
```

El agente puente de OpenClaw debe tener un perfil mínimo y no debe tener las
tools del dominio. Así se evita duplicar capacidades y se garantiza que las
tools permanecen bajo control de LangGraph.

Variables locales:

```env
NAYAX_LLM_PROVIDER=openclaw_gateway
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789/v1
OPENCLAW_GATEWAY_MODEL=openclaw/[PROJECT]-bridge
OPENCLAW_GATEWAY_TIMEOUT_SECONDS=120
```

El script local debe obtener el token desde la configuración de OpenClaw y
exportarlo únicamente durante la ejecución:

```bash
./scripts/run-openclaw-chat.sh --thread-id operador-local
./scripts/run-openclaw-studio.sh
```

No se debe commitear el token. Además, no debe existir en `.env` una línea
vacía como esta:

```env
OPENCLAW_GATEWAY_TOKEN=
```

LangGraph Studio puede cargar `.env` y sobrescribir el token dinámico del
script. Si se necesita una ejecución manual, el token debe exportarse fuera
del repositorio.

### 3.2 Preproducción y producción con API key

```env
NAYAX_LLM_PROVIDER=openai
OPENAI_API_KEY=[SECRET_FROM_SECRET_MANAGER]
NAYAX_LLM_MODEL=gpt-5.4-mini
NAYAX_LLM_TEMPERATURE=0
NAYAX_LLM_TIMEOUT_SECONDS=30
```

Ejecución:

```bash
uv run [project]-chat --thread-id operador-prod
uv run [project]-pricing-report
```

En producción la API key debe proceder de un gestor de secretos, variables
protegidas del despliegue o del entorno de ejecución. Nunca debe aparecer en
Git, logs o mensajes de error.

## 4. Configuración de `.env`

La plantilla `.env.example` debe separar claramente las variables comunes y
las específicas de cada proveedor:

```env
# Seleccionar solo un proveedor
NAYAX_LLM_PROVIDER=openai

# OpenAI para preproducción/producción
OPENAI_API_KEY=
NAYAX_LLM_MODEL=gpt-5.4-mini
NAYAX_LLM_TEMPERATURE=0
NAYAX_LLM_TIMEOUT_SECONDS=30

# OpenClaw para desarrollo local
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789/v1
# El token lo inyecta el script; no dejar una asignación vacía.
OPENCLAW_GATEWAY_MODEL=openclaw/[PROJECT]-bridge
OPENCLAW_GATEWAY_TIMEOUT_SECONDS=120

# LangSmith
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=[PROJECT_NAME]

# MCP y runtime
[PROJECT]_MCP_DIR=../[MCP_PROJECT]
[PROJECT]_NODE_COMMAND=node
[PROJECT]_CHECKPOINT_DB=data/checkpoints.db
```

Las variables del dominio deben añadirse en una sección separada:

```env
# Credenciales y configuración del dominio
[DOMAIN]_BASE_URL=
[DOMAIN]_CLIENT_ID=
[DOMAIN]_CLIENT_SECRET=
```

## 5. Estructura recomendada

```text
[project]/
├── config/                 # mappings y configuración no secreta
├── data/                   # datos locales, ignorados por Git
├── docs/                   # arquitectura, despliegue e integraciones
├── scripts/                # lanzadores locales por proveedor
├── src/[package]/
│   ├── domain/             # reglas puras y entidades
│   ├── graphs/             # grafos LangGraph y estados
│   ├── infrastructure/     # LLM, MCP, DB y clientes externos
│   ├── interfaces/         # CLI, Telegram, HTTP
│   └── prompts/            # prompts versionados
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── .env.example
├── langgraph.json
├── pyproject.toml
└── README.md
```

## 6. Reglas de Clean Code y SOLID

- El dominio no importa LangGraph, MCP, OpenAI, OpenClaw ni HTTP.
- Las interfaces dependen de casos de uso, no de implementaciones concretas.
- Los clientes externos se encapsulan detrás de puertos/adaptadores.
- Los cálculos críticos deben ser deterministas y testeables sin LLM.
- Los prompts deben estar versionados como archivos independientes.
- El estado de LangGraph debe tener un esquema claro y pequeño.
- Las tools deben tener nombres, descripciones y argumentos explícitos.
- Los errores externos deben transformarse en errores de aplicación legibles.
- Los secretos nunca se imprimen, serializan en logs ni se guardan en Git.
- Las dependencias deben inyectarse en los grafos para facilitar los tests.

## 7. LangGraph Studio y LangSmith

Declarar los grafos en `langgraph.json`:

```json
{
  "dependencies": ["."],
  "graphs": {
    "main": "./src/[package]/studio.py:make_main_graph"
  },
  "env": ".env"
}
```

Para ver trazas se necesita una `LANGSMITH_API_KEY` válida:

```env
LANGSMITH_API_KEY=lsv2_tu_clave_real
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=[PROJECT_NAME]
```

Arranque local:

```bash
# OpenClaw OAuth
./scripts/run-openclaw-studio.sh

# OpenAI API key
uv run --extra studio langgraph dev --no-browser
```

La factoría del grafo debe evitar inicializaciones costosas repetidas. En
particular, conviene cachear o reutilizar el modelo y el descubrimiento de
tools MCP, y evitar abrir conexiones externas cada vez que Studio consulta el
schema del grafo.

## 8. Checklist para crear una nueva lógica de agentes

- [ ] Copiar esta plantilla y sustituir los placeholders.
- [ ] Definir el dominio y sus reglas deterministas.
- [ ] Definir el estado de LangGraph.
- [ ] Separar los puertos de aplicación de los adaptadores externos.
- [ ] Implementar las tools MCP y su allowlist.
- [ ] Implementar el proveedor OpenAI.
- [ ] Implementar el adaptador OpenClaw local.
- [ ] Crear scripts `run-openclaw-chat.sh`, `run-openclaw-studio.sh` y pricing
      si aplica.
- [ ] Añadir `.env.example` sin secretos ni tokens vacíos problemáticos.
- [ ] Añadir tests unitarios del dominio y del adaptador LLM.
- [ ] Añadir tests de integración de MCP.
- [ ] Validar ambos proveedores con el mismo flujo.
- [ ] Validar `langgraph.json` y Studio.
- [ ] Ejecutar `ruff`, `mypy` y `pytest`.
- [ ] Confirmar que el proyecto original permanece intacto.

## 9. Comandos mínimos de calidad

```bash
uv run ruff check .
uv run mypy --no-incremental
uv run pytest -q
uv run langgraph validate
```

## 10. Decisión arquitectónica clave

OpenClaw y OpenAI son intercambiables como proveedores de inteligencia. No
son propietarios de la lógica del negocio ni de las tools. La aplicación debe
poder pasar de:

```text
OpenClaw OAuth local
```

a:

```text
OpenAI API key en preproducción/producción
```

modificando únicamente la configuración y los secretos del entorno.
