from __future__ import annotations

from pytest import MonkeyPatch

from invoice_bridge.vision import OpenAIVisionSettings


def test_openclaw_gateway_is_selected_without_openai_key(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("INVOICE_VISION_PROVIDER", "openclaw_gateway")
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "gateway-token")
    monkeypatch.setenv("OPENCLAW_GATEWAY_URL", "http://gateway.local/v1")
    monkeypatch.setenv("OPENCLAW_GATEWAY_MODEL", "openclaw/vision-agent")

    settings = OpenAIVisionSettings.from_environment()

    assert settings is not None
    assert settings.api_key == "gateway-token"
    assert settings.base_url == "http://gateway.local/v1"
    assert settings.model == "openclaw/vision-agent"
