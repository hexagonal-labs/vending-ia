from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any, cast
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from nayax_agents.infrastructure.messages import message_content_text


class OpenClawToolProtocolModel:
    """Modelo OpenClaw que deja la ejecución de tools en LangGraph.

    El Gateway OpenClaw de esta instalación no conserva ``client tools`` como
    tools nativas del agente OAuth. Para mantener la misma arquitectura,
    intercambiamos una pequeña respuesta JSON: OpenClaw decide entre pedir una
    tool o devolver la respuesta final; LangGraph valida y ejecuta la tool.
    """

    def __init__(self, model: Any, tools: Sequence[Any] = ()) -> None:
        self._model = model
        self._tools = tuple(tools)

    def bind_tools(self, tools: Sequence[Any], **_: Any) -> OpenClawToolProtocolModel:
        return OpenClawToolProtocolModel(self._model, tools)

    async def ainvoke(self, messages: Sequence[BaseMessage], **kwargs: Any) -> AIMessage:
        if not self._tools:
            return cast(AIMessage, await self._model.ainvoke(messages, **kwargs))

        response = await self._model.ainvoke(self._build_protocol_messages(messages), **kwargs)
        return self._parse_response(message_content_text(response))

    def _build_protocol_messages(self, messages: Sequence[BaseMessage]) -> list[BaseMessage]:
        system_prompts = [message_content_text(message) for message in messages if isinstance(message, SystemMessage)]
        transcript = "\n\n".join(
            self._render_message(message) for message in messages if not isinstance(message, SystemMessage)
        )
        tool_definitions = [
            {
                "name": getattr(tool, "name", ""),
                "description": getattr(tool, "description", ""),
                "arguments": getattr(tool, "args", {}),
            }
            for tool in self._tools
        ]
        protocol = (
            "Actúa únicamente como inteligencia para un orquestador externo. "
            "Nunca ejecutes herramientas tú mismo. Debes responder exclusivamente con un JSON válido, sin markdown. "
            "Si necesitas datos, devuelve: "
            '{"type":"tool_call","name":"<nombre>","arguments":{}}. '
            "Solo puedes pedir una herramienta de la lista disponible. "
            "Si ya tienes los resultados necesarios, devuelve: "
            '{"type":"final","content":"<respuesta para el usuario>"}.\n\n'
            "Herramientas disponibles:\n"
            f"{json.dumps(tool_definitions, ensure_ascii=False, default=str)}"
        )
        system_content = "\n\n".join([*system_prompts, protocol])
        return [SystemMessage(content=system_content), HumanMessage(content=transcript)]

    @staticmethod
    def _render_message(message: BaseMessage) -> str:
        role = getattr(message, "type", "message").upper()
        content = message_content_text(message)
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            content = f"{content}\nTOOL_CALLS: {json.dumps(tool_calls, ensure_ascii=False, default=str)}"
        return f"{role}: {content}"

    def _parse_response(self, content: str) -> AIMessage:
        payload = self._parse_json_object(content)
        if not isinstance(payload, dict):
            return AIMessage(content=content)

        if payload.get("type") == "final":
            final_content = payload.get("content", "")
            return AIMessage(content=final_content if isinstance(final_content, str) else str(final_content))

        if payload.get("type") != "tool_call":
            return AIMessage(content=content)

        name = payload.get("name")
        arguments = payload.get("arguments", {})
        available_names = {getattr(tool, "name", "") for tool in self._tools}
        if not isinstance(name, str) or name not in available_names:
            raise ValueError(f"OpenClaw pidió una tool no disponible: {name}")
        if not isinstance(arguments, dict):
            raise ValueError(f"Los argumentos de {name} deben ser un objeto JSON")

        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": name,
                    "args": arguments,
                    "id": f"call_{uuid4().hex}",
                    "type": "tool_call",
                }
            ],
        )

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any] | None:
        candidate = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL)
        if fenced:
            candidate = fenced.group(1)
        else:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start >= 0 and end > start:
                candidate = candidate[start : end + 1]
        try:
            payload = json.loads(candidate)
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None
