# Desarrollo local con OpenClaw OAuth

El proyecto soporta dos proveedores de LLM:

- `openai`: recomendado para preproducción y producción. LangGraph registra las
  tools MCP y las ejecuta dentro del grafo mediante `ToolNode`.
- `openclaw_gateway`: pensado para pruebas locales sin una `OPENAI_API_KEY`.
  LangGraph llama al endpoint OpenResponses del Gateway. OpenClaw aporta
  únicamente la inteligencia OAuth; LangGraph conserva la ejecución de las
  tools Nayax.

## Configuración del Gateway

El Gateway debe estar en loopback y tener habilitado OpenResponses:

```bash
openclaw config set gateway.http.endpoints.responses.enabled true
```

El agente dedicado `nayax-langgraph-bridge` no necesita ni debe tener las
tools Nayax. Solo recibe el prompt y devuelve el JSON de protocolo que le pide
LangGraph: una solicitud de tool o la respuesta final. El servidor MCP y las
tools de lectura se cargan desde este proyecto y se ejecutan mediante
`langgraph.prebuilt.ToolNode`.

Con OpenClaw OAuth/Codex, el agente necesita `tools.exec.mode=ask` para que el
harness pueda arrancar. El agente puente no debe recibir permisos de escritura
ni mensajería. El proyecto no modifica `nayax-agents/`.

## Ejecutar

Los scripts leen el token desde `~/.openclaw/openclaw.json` en tiempo de
ejecución. No lo copies a `.env`, no lo commitees y no lo imprimas:

```bash
./scripts/run-openclaw-chat.sh --thread-id operador-oauth
./scripts/run-openclaw-pricing.sh
./scripts/run-openclaw-studio.sh
```

El modo OpenClaw puede tardar bastante más que la API directa porque atraviesa
el Gateway y el harness OAuth. Es útil para desarrollo local;
la ruta de producción debe usar `NAYAX_LLM_PROVIDER=openai` y una API key
gestionada por el entorno de despliegue.

## Modelo mental

En modo `openai`:

```text
LangGraph -> ChatOpenAI -> tool call -> ToolNode -> nayax-bridge MCP
```

En modo `openclaw_gateway`:

```text
LangGraph -> OpenClaw (JSON protocol) -> LangGraph ToolNode -> nayax-bridge MCP
         -> OpenClaw (respuesta final) -> usuario
```

El adaptador `OpenClawToolProtocolModel` traduce la decisión JSON de OpenClaw a
un `AIMessage.tool_calls`. Así, `ToolNode` ejecuta exactamente las mismas tools
MCP que en el modo `openai`, y el resultado vuelve al historial antes de pedir
la redacción final. El cambio de proveedor no cambia el grafo ni la lógica de
negocio.

En esta instalación el runtime OAuth local de OpenClaw no expone de forma
fiable las `client tools` nativas del endpoint OpenResponses. El protocolo JSON
es un adaptador de compatibilidad: mantiene la propiedad de las tools, los
pasos visibles en LangGraph/Studio y la misma interfaz de cambio a API key.
