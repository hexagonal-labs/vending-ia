# Ejecutar nayax-agents-langgraph desde otro Mac usando OpenClaw remoto

Esta configuración permite ejecutar `nayax-agents-langgraph` en un Mac nuevo
sin instalar OpenClaw allí. OpenClaw permanece instalado y ejecutándose en el
Mac antiguo, que actúa como Gateway LLM remoto.

La conexión se realiza mediante un túnel SSH. El puerto del Gateway no se
expone públicamente.

## Arquitectura

```text
Mac nuevo
  LangGraph Studio
  nayax-agents-langgraph
  nayax-bridge
       |
       | localhost:18789 mediante túnel SSH
       v
Mac antiguo
  OpenClaw Gateway: 127.0.0.1:18789
```

El `nayax-bridge` y las herramientas MCP se ejecutan en el Mac nuevo. Solo
las peticiones al LLM pasan por el Gateway del Mac antiguo.

## Requisitos

### Mac antiguo

- OpenClaw instalado y configurado.
- Gateway de OpenClaw funcionando en `127.0.0.1:18789`.
- Acceso SSH habilitado.
- Accesible desde el Mac nuevo, preferiblemente mediante Tailscale.

### Mac nuevo

- Python 3.11 o superior.
- `uv`.
- Node.js 20 o superior.
- El proyecto `nayax-agents-langgraph`.
- El proyecto `nayax-bridge` compilado.
- Sus variables de conexión a Nayax en `nayax-bridge/.env`.
- El token del Gateway de OpenClaw, obtenido de forma segura.

## 1. Comprobar el Gateway en el Mac antiguo

En el Mac antiguo, comprobar que el Gateway está activo:

```bash
curl http://127.0.0.1:18789/v1/models
```

Si el endpoint OpenResponses no estuviera habilitado, activarlo en el Mac
antiguo:

```bash
openclaw config set gateway.http.endpoints.responses.enabled true
```

Después, reiniciar el Gateway de OpenClaw si fuera necesario.

El token se encuentra en la configuración local de OpenClaw:

```text
~/.openclaw/openclaw.json
```

No se debe subir, commitear ni pegar ese archivo completo en el proyecto.
Solo hay que transferir el token por un canal seguro.

## 2. Habilitar SSH en el Mac antiguo

En el Mac antiguo:

1. Abrir `Ajustes del Sistema`.
2. Ir a `General` → `Compartir`.
3. Activar `Inicio de sesión remoto`.
4. Anotar el usuario del Mac antiguo.

Si ambos equipos utilizan Tailscale, se puede conectar usando el nombre
Tailscale del Mac antiguo o su IP Tailscale en lugar de una IP pública.

Probar desde el Mac nuevo:

```bash
ssh usuario@mac-antiguo
```

También se puede usar directamente la IP Tailscale:

```bash
ssh usuario@100.x.y.z
```

## 3. Crear el túnel desde el Mac nuevo

En el Mac nuevo, abrir una terminal y dejar ejecutado:

```bash
ssh -N -L 18789:127.0.0.1:18789 usuario@mac-antiguo
```

Qué significa:

- `-N`: no abre una shell remota; mantiene únicamente el túnel.
- `-L 18789:127.0.0.1:18789`: el puerto local `18789` del Mac nuevo se
  redirige al puerto `18789` del Mac antiguo.

Mientras esta terminal esté activa, cualquier conexión a
`http://127.0.0.1:18789` desde el Mac nuevo llegará al Gateway del Mac antiguo.

Para evitar que el túnel se cierre por una conexión inactiva:

```bash
ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=3 \
  -N -L 18789:127.0.0.1:18789 usuario@mac-antiguo
```

No cerrar esta terminal mientras se utilice Studio.

## 4. Verificar el túnel desde el Mac nuevo

Con el túnel abierto, ejecutar en otra terminal del Mac nuevo:

```bash
curl http://127.0.0.1:18789/v1/models
```

Si devuelve una respuesta del Gateway, el túnel funciona.

Si falla:

- comprobar que OpenClaw sigue ejecutándose en el Mac antiguo;
- comprobar que el puerto local `18789` no está ocupado en el Mac nuevo;
- comprobar que SSH puede conectarse al Mac antiguo;
- revisar que ambos Macs tengan conectividad Tailscale.

## 5. Configurar el proyecto en el Mac nuevo

Desde la raíz de `nayax-agents-langgraph`, crear o ajustar `.env`:

```env
NAYAX_LLM_PROVIDER=openclaw_gateway
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789/v1
OPENCLAW_GATEWAY_MODEL=openclaw/nayax-langgraph-bridge
OPENCLAW_GATEWAY_TIMEOUT_SECONDS=120
OPENCLAW_GATEWAY_TOKEN=token-del-gateway
```

Sustituir `token-del-gateway` por el token real. No guardar este valor en Git
ni compartirlo en capturas o mensajes.

En esta configuración no es necesario instalar OpenClaw en el Mac nuevo.

## 6. Preparar y arrancar el proyecto

Desde el Mac nuevo:

```bash
cd /ruta/al/proyecto/nayax-agents-langgraph
uv sync --extra dev --extra studio
```

Comprobar que `nayax-bridge` está compilado:

```bash
cd ../nayax-bridge
npm run build
cd ../nayax-agents-langgraph
```

Arrancar LangGraph Studio manualmente:

```bash
uv run --extra studio langgraph dev --no-browser
```

Abrir la URL de Studio que muestre el comando, normalmente:

```text
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

El script `scripts/run-openclaw-studio.sh` no debe utilizarse directamente en
el Mac nuevo porque busca `~/.openclaw/openclaw.json` localmente. Ese script
está pensado para ejecutarse en un equipo donde OpenClaw está instalado.

## 7. Ejecutar el chat CLI

Con el túnel abierto y las variables cargadas:

```bash
uv run nayax-chat --thread-id operador-remoto
```

Para el informe de precios:

```bash
uv run nayax-pricing-report
```

## Seguridad

- Usar SSH sobre Tailscale siempre que sea posible.
- No publicar el puerto `18789` mediante Tailscale Funnel ni abrirlo en el
  router.
- No exponer el token del Gateway en el repositorio.
- No copiar `~/.openclaw/openclaw.json` completo al Mac nuevo.
- Si el token se filtra, regenerarlo desde la configuración de OpenClaw.

## Resumen de uso diario

En el Mac antiguo:

1. Mantener OpenClaw Gateway encendido.

En el Mac nuevo:

1. Abrir el túnel SSH.
2. Arrancar LangGraph Studio o el chat.
3. Cerrar Studio y el túnel al terminar.

