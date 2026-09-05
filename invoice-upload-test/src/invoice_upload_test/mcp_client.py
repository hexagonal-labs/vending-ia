from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class BridgeMcpClient:
    """Cliente de vida corta para que el proyecto de prueba use MCP real."""

    def __init__(
        self,
        bridge_dir: Path,
        module: str,
        python_command: str,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self._bridge_dir = bridge_dir
        self._module = module
        self._python_command = python_command
        self._extra_env = dict(extra_env or {})

    async def call(self, tool_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if not (self._bridge_dir / "src").is_dir():
            raise FileNotFoundError(f"No existe el bridge: {self._bridge_dir}")
        environment = dict(os.environ)
        source_path = str(self._bridge_dir / "src")
        environment["PYTHONPATH"] = source_path + (
            os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
        )
        environment.update(self._extra_env)
        parameters = StdioServerParameters(
            command=self._python_command,
            args=["-m", self._module],
            cwd=str(self._bridge_dir),
            env=environment,
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, dict(arguments))
        if result.isError:
            raise RuntimeError(_text_content(result.content) or f"Error MCP en {tool_name}")
        payload = _text_content(result.content)
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("El bridge devolvió un resultado no estructurado")
        return parsed


def _text_content(content: list[Any]) -> str:
    return "".join(str(getattr(item, "text", "")) for item in content)
