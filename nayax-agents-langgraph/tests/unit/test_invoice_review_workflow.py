from __future__ import annotations

from typing import Any

import pytest

from nayax_agents.application.invoice_review_workflow import InvoiceReviewWorkflow


class FakeTool:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def ainvoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(arguments)
        return self.response


@pytest.mark.asyncio
async def test_upload_then_extract_uses_the_durable_uri_returned_by_invoice_bridge() -> None:
    uploaded = FakeTool({"sourceUri": "/var/lib/invoice-bridge/uploads/a-invoice.pdf"})
    extracted = FakeTool({"sourceHash": "a" * 64, "status": "EXTRACTED", "lines": []})
    workflow = InvoiceReviewWorkflow(
        {"upload_invoice": uploaded, "extract_invoice": extracted},
        {},
    )

    result = await workflow.extract(filename="invoice.pdf", content_base64="ZmFrZS1wZGY=")

    assert uploaded.calls == [{"filename": "invoice.pdf", "content_base64": "ZmFrZS1wZGY="}]
    assert extracted.calls == [
        {"source_uri": "/var/lib/invoice-bridge/uploads/a-invoice.pdf", "supplier_id": None}
    ]
    assert result["sourceUri"] == "/var/lib/invoice-bridge/uploads/a-invoice.pdf"


@pytest.mark.asyncio
async def test_import_has_a_stable_idempotency_key_and_configured_surcharge() -> None:
    recorded = FakeTool({"insertedOffers": 2, "duplicate": False})
    workflow = InvoiceReviewWorkflow({}, {"record_supplier_invoice": recorded}, equivalence_surcharge_rate="0.052")
    invoice = {"sourceHash": "b" * 64, "status": "EXTRACTED", "lines": []}

    result = await workflow.import_invoice(invoice)

    assert result["insertedOffers"] == 2
    assert recorded.calls == [
        {
            "invoice": invoice,
            "idempotency_key": f"invoice-{'b' * 64}",
            "equivalence_surcharge_rate": "0.052",
        }
    ]
