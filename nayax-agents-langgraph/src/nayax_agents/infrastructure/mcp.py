from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

INFO_TOOL_NAMES = frozenset(
    {
        "list_machines",
        "list_machine_products",
        "get_sales_summary",
        "get_sales_by_machine",
    }
)

_INHERITED_PROCESS_ENV_NAMES = (
    "HOME",
    "LOGNAME",
    "PATH",
    "SHELL",
    "TERM",
    "USER",
)

# El cliente MCP filtra por defecto el entorno del proceso hijo. El bridge
# necesita estas variables porque en Docker no se copia ningun .env a la imagen.
_BRIDGE_ENV_NAMES = (
    "NODE_ENV",
    "LOG_LEVEL",
    "HTTP_PORT",
    "HTTP_HOST",
    "NAYAX_BASE_URL",
    "NAYAX_API_PREFIX",
    "NAYAX_TOKEN",
    "NAYAX_OPERATOR_ID",
    "NAYAX_TIMEOUT_MS",
    "NAYAX_MAX_RETRIES",
    "API_KEYS",
    "MAX_PRICE_CHANGE_RATIO",
    "WRITES_ENABLED",
    "MCP_WRITES_REQUIRE_DRY_RUN",
    "CACHE_TTL_SECONDS",
    # Configuración del bridge de proveedores. El cliente MCP crea los
    # subprocesos con un entorno explícito, por lo que estas variables no se
    # heredan si no se incluyen aquí.
    "DISTRIBUIDORA_MAYORISTA_BASE_URL",
    "DISTRIBUIDORA_MAYORISTA_EMAIL",
    "DISTRIBUIDORA_MAYORISTA_PASSWORD",
    "DISTRIBUIDORA_MAYORISTA_WISHLIST_ID",
    "DISTRIBUIDORA_MAYORISTA_PRICE_INCLUDES_VAT",
    "DISTRIBUIDORA_MAYORISTA_PRICE_INCLUDES_EQUIVALENCE_SURCHARGE",
    "DISTRIBUIDORA_MAYORISTA_VAT_RATE",
    "DISTRIBUIDORA_MAYORISTA_EQUIVALENCE_SURCHARGE_RATE",
    # invoice-bridge se inicia como proceso MCP hijo. Debe heredar la
    # configuración de visión para poder usar el agente OCR remoto, sin que el
    # grafo o el bridge de Nayax tengan que conocer sus secretos.
    "INVOICE_VISION_PROVIDER",
    "INVOICE_VISION_MODEL",
    "INVOICE_VISION_TIMEOUT_SECONDS",
    "INVOICE_VISION_MAX_ATTEMPTS",
    "INVOICE_DATA_DIR",
    "OPENCLAW_GATEWAY_URL",
    "OPENCLAW_GATEWAY_TOKEN",
    "OPENCLAW_GATEWAY_MODEL",
    "OPENCLAW_GATEWAY_TIMEOUT_SECONDS",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
)


def _bridge_environment() -> dict[str, str]:
    """Construye el entorno mínimo necesario para el proceso MCP de Nayax."""
    names = (*_INHERITED_PROCESS_ENV_NAMES, *_BRIDGE_ENV_NAMES)
    return {name: value for name in names if (value := os.environ.get(name)) is not None}


def build_nayax_mcp_client(bridge_dir: Path, node_command: str = "node") -> Any:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    server_path = bridge_dir / "dist" / "mcp.js"
    if not server_path.is_file():
        raise FileNotFoundError(f"No existe el servidor MCP compilado: {server_path}")

    servers: dict[str, Any] = {
            "nayax": {
                "transport": "stdio",
                "command": node_command,
                "args": [str(server_path)],
                "cwd": str(bridge_dir),
                "env": _bridge_environment(),
            }
    }
    return MultiServerMCPClient(servers)


def build_pricing_mcp_client(
    *,
    nayax_bridge_dir: Path,
    supplier_bridge_dir: Path,
    pricing_catalog_bridge_dir: Path,
    invoice_bridge_dir: Path,
    nayax_node_command: str = "node",
    python_command: str = sys.executable,
    pricing_data_dir: Path = Path("data/pricing"),
    pricing_export_dir: Path = Path("reports"),
) -> Any:
    """Conecta el núcleo a bridges aislados; ningún bridge llama a otro."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    nayax_server = nayax_bridge_dir / "dist" / "mcp.js"
    if not nayax_server.is_file():
        raise FileNotFoundError(f"No existe el servidor MCP compilado: {nayax_server}")
    for bridge_dir in (supplier_bridge_dir, pricing_catalog_bridge_dir, invoice_bridge_dir):
        if not (bridge_dir / "src").is_dir():
            raise FileNotFoundError(f"No existe el código fuente MCP: {bridge_dir / 'src'}")
    servers: dict[str, Any] = {
            "nayax": {
                "transport": "stdio",
                "command": nayax_node_command,
                "args": [str(nayax_server)],
                "cwd": str(nayax_bridge_dir),
                "env": _bridge_environment(),
            },
            "supplier": _python_mcp_server(
                supplier_bridge_dir,
                "supplier_bridge.interfaces.mcp_server",
                python_command,
            ),
            "pricing_catalog": _python_mcp_server(
                pricing_catalog_bridge_dir,
                "pricing_catalog_bridge.interfaces.mcp_server",
                python_command,
                {
                    "PRICING_DATA_DIR": str(pricing_data_dir),
                    "PRICING_EXPORT_DIR": str(pricing_export_dir),
                },
            ),
            "invoice": _python_mcp_server(invoice_bridge_dir, "invoice_bridge.server", python_command),
    }
    return MultiServerMCPClient(servers)


def _python_mcp_server(
    bridge_dir: Path, module: str, python_command: str, extra_env: dict[str, str] | None = None
) -> dict[str, Any]:
    environment = _bridge_environment()
    existing_python_path = os.environ.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(bridge_dir / "src") + (
        os.pathsep + existing_python_path if existing_python_path else ""
    )
    if extra_env:
        environment.update(extra_env)
    local_venv_python = bridge_dir / ".venv" / "bin" / "python"
    if python_command == "python" and local_venv_python.is_file():
        command = str(local_venv_python)
    elif python_command == "python":
        # En Docker los bridges se copian sin su propio virtualenv. Usamos el
        # intérprete que ejecuta LangGraph, que ya contiene mcp y dependencias
        # compartidas, en lugar del Python global del sistema.
        command = sys.executable
    else:
        command = python_command
    return {
        "transport": "stdio",
        "command": command,
        "args": ["-m", module],
        "cwd": str(bridge_dir),
        "env": environment,
    }


async def load_info_tools(client: Any) -> list[Any]:
    tools = await client.get_tools()
    return [tool for tool in tools if getattr(tool, "name", "") in INFO_TOOL_NAMES]


async def load_read_tools(client: Any) -> dict[str, Any]:
    tools = await client.get_tools()
    return {
        tool.name: tool
        for tool in tools
        if getattr(tool, "name", "") in INFO_TOOL_NAMES or getattr(tool, "name", "") == "get_price_change_history"
    }


def group_pricing_tools(tools: list[Any]) -> dict[str, dict[str, Any]]:
    """Agrupa tools de una conexión MultiServer, incluso si están prefijadas."""
    groups: dict[str, dict[str, Any]] = {"nayax": {}, "supplier": {}, "pricing_catalog": {}, "invoice": {}}
    for tool in tools:
        name = str(getattr(tool, "name", ""))
        for server, group in groups.items():
            bare = name.removeprefix(f"{server}_").removeprefix(f"{server}__")
            if name.startswith(f"{server}_") or name.startswith(f"{server}__"):
                group[bare] = tool
        if name in {"list_machines", "list_machine_products"}:
            groups["nayax"][name] = tool
        elif name == "fetch_supplier_offers":
            groups["supplier"][name] = tool
        elif name in {
            "record_supplier_snapshot",
            "record_supplier_invoice",
            "list_catalog_providers",
            "match_products",
            "generate_machine_supplier_report",
        }:
            groups["pricing_catalog"][name] = tool
        elif name in {"archive_invoice", "upload_invoice", "extract_invoice", "revise_extracted_invoice"}:
            groups["invoice"][name] = tool
    return groups
