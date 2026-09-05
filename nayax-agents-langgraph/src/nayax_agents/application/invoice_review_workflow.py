"""Orquestación de extracción, revisión humana e importación de facturas."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


class InvoiceReviewWorkflow:
    """Coordina los MCP de factura y catálogo sin delegar validaciones al LLM."""

    def __init__(
        self,
        invoice_tools: Mapping[str, Any],
        catalog_tools: Mapping[str, Any],
        *,
        equivalence_surcharge_rate: str = "0.052",
    ) -> None:
        self._invoice_tools = invoice_tools
        self._catalog_tools = catalog_tools
        self._equivalence_surcharge_rate = equivalence_surcharge_rate

    async def extract(
        self,
        source_uri: str | None = None,
        supplier_id: str | None = None,
        *,
        filename: str | None = None,
        content_base64: str | None = None,
    ) -> dict[str, Any]:
        """Archiva una ruta accesible al bridge o un adjunto Base64 de un chat."""
        has_source = bool(source_uri and source_uri.strip())
        has_upload = bool(filename and content_base64)
        if has_source == has_upload:
            raise ValueError("Indica exactamente source_uri o filename y content_base64.")
        if has_upload:
            archived = _mapping(
                await _invoke(
                    self._invoice_tools,
                    "upload_invoice",
                    {"filename": filename, "content_base64": content_base64},
                )
            )
        else:
            assert source_uri is not None
            archived = _mapping(await _invoke(self._invoice_tools, "archive_invoice", {"source_uri": source_uri}))
        archived_uri = str(archived["sourceUri"])
        invoice = _mapping(
            await _invoke(
                self._invoice_tools,
                "extract_invoice",
                {"source_uri": archived_uri, "supplier_id": supplier_id},
            )
        )
        return {"sourceUri": archived_uri, "invoice": dict(invoice)}

    async def revise(self, invoice: Mapping[str, Any], corrections: list[dict[str, Any]]) -> dict[str, Any]:
        if not corrections:
            raise ValueError("Debes indicar al menos una corrección.")
        return dict(
            _mapping(
                await _invoke(
                    self._invoice_tools,
                    "revise_extracted_invoice",
                    {"invoice": dict(invoice), "corrections": corrections},
                )
            )
        )

    async def import_invoice(self, invoice: Mapping[str, Any]) -> dict[str, Any]:
        if invoice.get("status") != "EXTRACTED":
            raise ValueError("La factura debe estar completamente validada antes de importarla.")
        source_hash = str(invoice.get("sourceHash", "")).strip()
        if not source_hash:
            raise ValueError("La factura no incluye sourceHash para garantizar la idempotencia.")
        return dict(
            _mapping(
                await _invoke(
                    self._catalog_tools,
                    "record_supplier_invoice",
                    {
                        "invoice": dict(invoice),
                        "idempotency_key": f"invoice-{source_hash}",
                        "equivalence_surcharge_rate": self._equivalence_surcharge_rate,
                    },
                )
            )
        )


async def _invoke(tools: Mapping[str, Any], name: str, arguments: dict[str, Any]) -> Any:
    tool = tools.get(name)
    if tool is None:
        raise RuntimeError(f"La tool MCP requerida no está disponible: {name}")
    return await tool.ainvoke(arguments)


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, Mapping):
            return parsed
    if isinstance(value, list):
        text = "".join(str(item.get("text", "")) for item in value if isinstance(item, Mapping))
        parsed = json.loads(text)
        if isinstance(parsed, Mapping):
            return parsed
    raise ValueError(f"Respuesta MCP no estructurada: {value!r}")
