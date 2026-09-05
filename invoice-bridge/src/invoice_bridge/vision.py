"""Adaptador de visión para facturas fotografiadas o PDF escaneados."""

from __future__ import annotations

import base64
import mimetypes
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

class VisionExtractionError(RuntimeError):
    """La factura no pudo extraerse de forma fiable mediante visión."""


class VisionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class VisionLine(VisionModel):
    raw_description: str = Field(alias="rawDescription")
    supplier_reference: str | None = Field(default=None, alias="supplierReference")
    barcode: str | None = None
    purchase_quantity: Decimal | None = Field(default=None, alias="purchaseQuantity")
    price_per_pack_net: Decimal | None = Field(default=None, alias="pricePerPackNet")
    discount_percent: Decimal | None = Field(default=None, alias="discountPercent")
    line_total_net: Decimal | None = Field(default=None, alias="lineTotalNet")
    vat_rate: Decimal | None = Field(default=None, alias="vatRate")
    pack_expression: str | None = Field(default=None, alias="packExpression")
    units_per_pack: Decimal | None = Field(default=None, alias="unitsPerPack")


class VisionInvoice(VisionModel):
    provider_id: str | None = Field(default=None, alias="providerId")
    supplier_name: str | None = Field(default=None, alias="supplierName")
    invoice_number: str | None = Field(default=None, alias="invoiceNumber")
    lines: list[VisionLine] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class OpenAIVisionSettings:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    max_attempts: int

    @classmethod
    def from_environment(cls) -> OpenAIVisionSettings | None:
        provider = os.getenv("INVOICE_VISION_PROVIDER", "").strip().lower()
        if not provider:
            provider = "openclaw_gateway" if os.getenv("OPENCLAW_GATEWAY_TOKEN") else "openai"
        if provider == "openclaw_gateway":
            api_key = os.getenv("OPENCLAW_GATEWAY_TOKEN", "").strip()
            base_url = os.getenv("OPENCLAW_GATEWAY_URL", "").rstrip("/")
            model = os.getenv("INVOICE_VISION_MODEL", "").strip() or os.getenv("OPENCLAW_GATEWAY_MODEL", "")
            timeout_seconds = float(
                os.getenv("INVOICE_VISION_TIMEOUT_SECONDS", os.getenv("OPENCLAW_GATEWAY_TIMEOUT_SECONDS", "120"))
            )
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            model = os.getenv("INVOICE_VISION_MODEL", "gpt-5-mini")
            timeout_seconds = float(os.getenv("INVOICE_VISION_TIMEOUT_SECONDS", "60"))
        else:
            raise ValueError(f"Proveedor de visión no soportado: {provider}")
        if not api_key:
            return None
        if not base_url or not model:
            raise ValueError("Falta la URL o el modelo de visión del proveedor configurado")
        return cls(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            max_attempts=_max_attempts(),
        )


def vision_configuration() -> dict[str, object]:
    """Diagnóstico sin secretos para operar el bridge desde una interfaz."""
    provider = os.getenv("INVOICE_VISION_PROVIDER", "").strip().lower()
    if not provider:
        provider = "openclaw_gateway" if os.getenv("OPENCLAW_GATEWAY_TOKEN") else "openai"
    if provider == "openclaw_gateway":
        return {
            "provider": provider,
            "tokenConfigured": bool(os.getenv("OPENCLAW_GATEWAY_TOKEN")),
            "urlConfigured": bool(os.getenv("OPENCLAW_GATEWAY_URL")),
            "model": os.getenv("INVOICE_VISION_MODEL", "").strip() or os.getenv("OPENCLAW_GATEWAY_MODEL", ""),
            "maxAttempts": _max_attempts(),
        }
    return {
        "provider": provider,
        "tokenConfigured": bool(os.getenv("OPENAI_API_KEY")),
        "urlConfigured": bool(os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")),
        "model": os.getenv("INVOICE_VISION_MODEL", "gpt-5-mini"),
        "maxAttempts": _max_attempts(),
    }


class OpenAIVisionExtractor:
    """Envía sólo el documento actual y pide datos de factura estructurados."""

    def __init__(self, settings: OpenAIVisionSettings) -> None:
        self._settings = settings

    def extract(self, path: Path, data: bytes) -> VisionInvoice:
        last_error: ValueError | None = None
        for attempt in range(1, self._settings.max_attempts + 1):
            request_body: dict[str, Any] = {
                "model": self._settings.model,
                "store": False,
                "max_output_tokens": 4000,
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            _instruction(retry=attempt > 1),
                            _document_content(path, data, self._settings.provider),
                        ],
                    }
                ],
            }
            if self._settings.provider != "openclaw_gateway":
                request_body["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": "supplier_invoice",
                        "strict": True,
                        "schema": VisionInvoice.model_json_schema(by_alias=True),
                    }
                }
            response = httpx.post(
                f"{self._settings.base_url}/responses",
                headers={"Authorization": f"Bearer {self._settings.api_key}"},
                json=request_body,
                timeout=self._settings.timeout_seconds,
            )
            if response.is_error:
                raise VisionExtractionError(_request_error_message(response))
            try:
                return VisionInvoice.model_validate_json(_output_text(response.json()))
            except (TypeError, ValueError) as error:
                last_error = ValueError(f"La respuesta de visión no cumple el contrato: {error}")
        assert last_error is not None
        raise VisionExtractionError(str(last_error)) from last_error


def extract_with_configured_vision(path: Path, data: bytes) -> VisionInvoice:
    settings = OpenAIVisionSettings.from_environment()
    if settings is None:
        raise VisionExtractionError("No hay un proveedor de visión configurado para extraer la factura.")
    return OpenAIVisionExtractor(settings).extract(path, data)


def _document_content(path: Path, data: bytes, provider: str) -> dict[str, Any]:
    encoded = base64.b64encode(data).decode("ascii")
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    if provider == "openclaw_gateway":
        if path.suffix.lower() == ".pdf":
            return {
                "type": "input_file",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": encoded,
                    "filename": path.name,
                },
            }
        return {
            "type": "input_image",
            "source": {"type": "base64", "media_type": mime_type, "data": encoded},
        }
    if path.suffix.lower() == ".pdf":
        return {"type": "input_file", "filename": path.name, "file_data": encoded}
    return {"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}", "detail": "high"}


def _instruction(*, retry: bool = False) -> dict[str, str]:
    retry_instruction = (
        " El intento anterior no devolvió JSON válido: responde exclusivamente con el objeto JSON solicitado, "
        "sin markdown, comentarios ni texto adicional."
        if retry
        else ""
    )
    return {
        "type": "input_text",
        "text": (
            "Extrae esta factura de proveedor. No adivines valores: usa null cuando un campo no sea legible. "
            "Identifica CASHORECA como providerId 'cashoreca'; para otro proveedor devuelve null. "
            "Devuelve exclusivamente un objeto JSON sin markdown ni campos adicionales con las claves "
            "providerId, supplierName, invoiceNumber y lines. Cada elemento de lines debe usar exclusivamente "
            "rawDescription, supplierReference, barcode, purchaseQuantity, pricePerPackNet, discountPercent, "
            "lineTotalNet, vatRate, packExpression y unitsPerPack. No uses los nombres de columna en español "
            "(referencia, ean, articulo, cantid, preu, importe) ni incluyas invoiceDate, currency o totals. "
            "Cada línea debe reflejar REFERENCIA, EAN, ARTÍCULO, CANTID, PRE/U, DTO%, IMPORTE e IVA si existen. "
            "pricePerPackNet es PRE/U neto del pack antes de descuento; lineTotalNet es IMPORTE neto. "
            "Reconoce expresiones de pack como 1*24 y 40G*14 y devuelve unitsPerPack=24 o 14 respectivamente. "
            "IVA debe ser fracción (21% => 0.21)."
            f"{retry_instruction}"
        ),
    }


def _max_attempts() -> int:
    raw_value = os.getenv("INVOICE_VISION_MAX_ATTEMPTS", "2")
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError("INVOICE_VISION_MAX_ATTEMPTS debe ser un entero entre 1 y 3") from error
    if value < 1 or value > 3:
        raise ValueError("INVOICE_VISION_MAX_ATTEMPTS debe estar entre 1 y 3")
    return value


def _output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                parts.append(content["text"])
    if not parts:
        raise ValueError("La respuesta de visión no contiene JSON")
    return "".join(parts)


def _request_error_message(response: httpx.Response) -> str:
    status = response.status_code
    category = {
        401: "token del Gateway inválido o no enviado",
        403: "token sin permiso para usar el Gateway",
        404: "URL del Gateway o endpoint /responses no disponible",
        400: "el Gateway, modelo o formato de documento no admite esta entrada visual",
        415: "formato de imagen o PDF no admitido por el Gateway",
    }.get(status, "error del Gateway o del modelo de visión")
    detail = _error_detail(response)
    suffix = f" Detalle del Gateway: {detail}" if detail else ""
    return f"HTTP {status}: {category}.{suffix}"


def _error_detail(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    message = error.get("message") if isinstance(error, dict) else payload.get("message")
    if not isinstance(message, str):
        return None
    # El Gateway no debe devolver secretos en sus errores; aun así limitamos el
    # dato operativo para que los logs no reflejen contenido del documento.
    return message.replace("\n", " ")[:300]
