#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
openclaw_config="${HOME}/.openclaw/openclaw.json"

if [[ ! -f "${openclaw_config}" ]]; then
  echo "No existe ${openclaw_config}. Instala/configura OpenClaw primero." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq es necesario para leer el token local del Gateway sin guardarlo en el proyecto." >&2
  exit 1
fi

gateway_token="$(jq -r '.gateway.auth.token // empty' "${openclaw_config}")"
if [[ -z "${gateway_token}" ]]; then
  echo "No se encontró gateway.auth.token en ${openclaw_config}." >&2
  exit 1
fi

if command -v uv >/dev/null 2>&1; then
  uv_command=(uv)
else
  uv_command=("${project_dir}/.tools/bin/uv")
fi

export NAYAX_LLM_PROVIDER=openclaw_gateway
export OPENCLAW_GATEWAY_TOKEN="${gateway_token}"
exec "${uv_command[@]}" run nayax-pricing-report "$@"
