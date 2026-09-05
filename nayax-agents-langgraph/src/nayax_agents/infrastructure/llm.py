from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from nayax_agents.infrastructure.config import Settings
from nayax_agents.infrastructure.openclaw_model import OpenClawToolProtocolModel


def build_chat_model(settings: Settings) -> Any:
    from langchain_openai import ChatOpenAI

    if settings.nayax_llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("Falta OPENAI_API_KEY en el entorno")

        options: dict[str, Any] = {
            "model": settings.nayax_llm_model,
            "api_key": SecretStr(settings.openai_api_key),
            "temperature": settings.nayax_llm_temperature,
            "timeout": settings.nayax_llm_timeout_seconds,
        }
        if settings.openai_base_url:
            options["base_url"] = settings.openai_base_url
        return ChatOpenAI(**options)

    if settings.nayax_llm_provider == "openclaw_gateway":
        if not settings.openclaw_gateway_token:
            raise RuntimeError(
                "Falta OPENCLAW_GATEWAY_TOKEN. Usa scripts/run-openclaw-chat.sh "
                "o configura el token del Gateway en el entorno."
            )

        gateway_model = ChatOpenAI(
            model=settings.openclaw_gateway_model,
            api_key=SecretStr(settings.openclaw_gateway_token),
            base_url=settings.openclaw_gateway_url,
            temperature=settings.nayax_llm_temperature,
            timeout=settings.openclaw_gateway_timeout_seconds,
            use_responses_api=True,
        )
        return OpenClawToolProtocolModel(gateway_model)

    raise RuntimeError(f"Proveedor LLM no soportado: {settings.nayax_llm_provider}")
