from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from nayax_agents.graphs.invoice_review_graph import build_invoice_review_graph


class FakeInvoiceWorkflow:
    def __init__(self) -> None:
        self.revisions: list[list[dict[str, Any]]] = []
        self.imports: list[dict[str, Any]] = []

    async def extract(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "sourceUri": "/var/lib/invoice-bridge/uploads/factura.pdf",
            "invoice": {
                "status": "REVIEW_REQUIRED",
                "sourceHash": "a" * 64,
                "lines": [{"validationStatus": "REVIEW_REQUIRED"}],
            },
        }

    async def revise(self, invoice: Mapping[str, Any], corrections: list[dict[str, Any]]) -> dict[str, Any]:
        self.revisions.append(corrections)
        return {**invoice, "status": "EXTRACTED", "lines": [{"validationStatus": "VALID"}]}

    async def import_invoice(self, invoice: Mapping[str, Any]) -> dict[str, Any]:
        self.imports.append(dict(invoice))
        return {"insertedOffers": 1}


@pytest.mark.asyncio
async def test_invoice_graph_pauses_for_employee_review_then_confirmation() -> None:
    workflow = FakeInvoiceWorkflow()
    graph = build_invoice_review_graph(workflow, MemorySaver())
    config = {"configurable": {"thread_id": "invoice-review-test"}}

    first = await graph.ainvoke({"source_uri": "/tmp/invoice.pdf"}, config=config)
    assert first["__interrupt__"][0].value["kind"] == "invoice_review"

    second = await graph.ainvoke(
        Command(resume={"action": "apply", "corrections": [{"lineIndex": 0, "unitsPerPack": "1"}]}),
        config=config,
    )
    assert workflow.revisions == [[{"lineIndex": 0, "unitsPerPack": "1"}]]
    assert second["__interrupt__"][0].value["kind"] == "invoice_import_confirmation"

    result = await graph.ainvoke(Command(resume={"approved": True}), config=config)
    assert result["status"] == "imported"
    assert result["import_result"] == {"insertedOffers": 1}
    assert len(workflow.imports) == 1


@pytest.mark.asyncio
async def test_invoice_graph_accepts_a_json_string_from_studio_when_resuming() -> None:
    graph = build_invoice_review_graph(FakeInvoiceWorkflow(), MemorySaver())
    config = {"configurable": {"thread_id": "invoice-review-studio-string-test"}}

    await graph.ainvoke({"source_uri": "/tmp/invoice.pdf"}, config=config)
    result = await graph.ainvoke(
        Command(resume=json.dumps({"action": "apply", "corrections": [{"lineIndex": 0, "unitsPerPack": "1"}]})),
        config=config,
    )

    assert result["__interrupt__"][0].value["kind"] == "invoice_import_confirmation"
