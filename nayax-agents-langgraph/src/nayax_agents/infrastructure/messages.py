from __future__ import annotations

from typing import Any


def message_content_text(message: Any) -> str:
    """Normaliza contenido LangChain de Chat Completions y Responses API."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
            else:
                text = getattr(block, "text", None)
            if isinstance(text, str):
                text_parts.append(text)
        if text_parts:
            return "\n".join(text_parts)
    return str(content)
