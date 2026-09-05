from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch, raises

from invoice_bridge.vision import OpenAIVisionExtractor, OpenAIVisionSettings, VisionExtractionError


def test_openclaw_gateway_is_selected_without_openai_key(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("INVOICE_VISION_MODEL", raising=False)
    monkeypatch.setenv("INVOICE_VISION_PROVIDER", "openclaw_gateway")
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "gateway-token")
    monkeypatch.setenv("OPENCLAW_GATEWAY_URL", "http://gateway.local/v1")
    monkeypatch.setenv("OPENCLAW_GATEWAY_MODEL", "openclaw/vision-agent")

    settings = OpenAIVisionSettings.from_environment()

    assert settings is not None
    assert settings.api_key == "gateway-token"
    assert settings.base_url == "http://gateway.local/v1"
    assert settings.model == "openclaw/vision-agent"
    assert settings.provider == "openclaw_gateway"
    assert settings.max_attempts == 2


def test_openclaw_uses_native_file_input_and_dedicated_vision_model(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("INVOICE_VISION_PROVIDER", "openclaw_gateway")
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "gateway-token")
    monkeypatch.setenv("OPENCLAW_GATEWAY_URL", "http://gateway.local/v1")
    monkeypatch.setenv("INVOICE_VISION_MODEL", "openclaw/nayax-invoice-vision")
    requests: list[dict[str, object]] = []

    class Response:
        is_error = False

        def json(self) -> dict[str, str]:
            return {"output_text": json.dumps({"providerId": "cashoreca", "lines": []})}

    def post(*_args: object, **kwargs: object) -> Response:
        requests.append(dict(kwargs))
        return Response()

    monkeypatch.setattr("invoice_bridge.vision.httpx.post", post)
    settings = OpenAIVisionSettings.from_environment()

    assert settings is not None
    result = OpenAIVisionExtractor(settings).extract(Path("invoice.pdf"), b"pdf-bytes")

    assert result.provider_id == "cashoreca"
    assert len(requests) == 1
    payload = requests[0]["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == "openclaw/nayax-invoice-vision"
    assert payload["input"][0]["type"] == "message"
    assert "text" not in payload
    content = payload["input"][0]["content"]
    assert content[1]["type"] == "input_file"
    assert content[1]["source"]["media_type"] == "application/pdf"
    assert "supplierReference" in content[0]["text"]


def test_invalid_vision_json_retries_once(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("INVOICE_VISION_PROVIDER", "openclaw_gateway")
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "gateway-token")
    monkeypatch.setenv("OPENCLAW_GATEWAY_URL", "http://gateway.local/v1")
    monkeypatch.setenv("INVOICE_VISION_MODEL", "openclaw/nayax-invoice-vision")
    calls: list[dict[str, object]] = []

    class Response:
        is_error = False

        def __init__(self, output_text: str) -> None:
            self._output_text = output_text

        def json(self) -> dict[str, str]:
            return {"output_text": self._output_text}

    responses = iter([Response("no es JSON"), Response('{"providerId":"cashoreca","lines":[]}')])

    def post(*_args: object, **kwargs: object) -> Response:
        calls.append(dict(kwargs))
        return next(responses)

    monkeypatch.setattr("invoice_bridge.vision.httpx.post", post)
    settings = OpenAIVisionSettings.from_environment()

    assert settings is not None
    result = OpenAIVisionExtractor(settings).extract(Path("invoice.jpg"), b"image-bytes")

    assert result.provider_id == "cashoreca"
    assert len(calls) == 2
    second_prompt = calls[1]["json"]["input"][0]["content"][0]["text"]
    assert "exclusivamente" in second_prompt


def test_gateway_error_is_propagated_without_fallback(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("INVOICE_VISION_PROVIDER", "openclaw_gateway")
    monkeypatch.setenv("OPENCLAW_GATEWAY_TOKEN", "gateway-token")
    monkeypatch.setenv("OPENCLAW_GATEWAY_URL", "http://gateway.local/v1")
    monkeypatch.setenv("INVOICE_VISION_MODEL", "openclaw/nayax-invoice-vision")

    class Response:
        is_error = True
        status_code = 400

        def json(self) -> dict[str, dict[str, str]]:
            return {"error": {"message": "Documento no compatible"}}

    monkeypatch.setattr("invoice_bridge.vision.httpx.post", lambda *_args, **_kwargs: Response())
    settings = OpenAIVisionSettings.from_environment()

    assert settings is not None
    with raises(VisionExtractionError, match="HTTP 400.*Documento no compatible"):
        OpenAIVisionExtractor(settings).extract(Path("invoice.pdf"), b"pdf-bytes")
