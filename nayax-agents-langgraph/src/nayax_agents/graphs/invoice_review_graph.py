"""Grafo HITL para que el empleado revise su propia factura antes de importarla."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal, Protocol, TypedDict


class InvoiceReviewOperations(Protocol):
    async def extract(
        self,
        source_uri: str | None = None,
        supplier_id: str | None = None,
        *,
        filename: str | None = None,
        content_base64: str | None = None,
    ) -> dict[str, Any]: ...

    async def revise(self, invoice: Mapping[str, Any], corrections: list[dict[str, Any]]) -> dict[str, Any]: ...

    async def import_invoice(self, invoice: Mapping[str, Any]) -> dict[str, Any]: ...


class InvoiceReviewState(TypedDict, total=False):
    # Un frontend/chat envía filename + content_base64; source_uri queda para
    # documentos que ya estén en el volumen compartido del servidor.
    source_uri: str | None
    filename: str | None
    content_base64: str | None
    supplier_id: str | None
    archived_source_uri: str
    invoice: dict[str, Any]
    status: Literal["extracting", "reviewing", "awaiting_confirmation", "imported", "cancelled"]
    review_response: dict[str, Any]
    review_error: str | None
    confirmation: dict[str, Any]
    import_result: dict[str, Any]
    final_reply: str


def build_invoice_review_graph(workflow: InvoiceReviewOperations, checkpointer: Any = None) -> Any:
    """Construye el workflow con pausas explícitas para corrección y confirmación."""
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    async def extract_document(state: InvoiceReviewState) -> dict[str, Any]:
        result = await workflow.extract(
            state.get("source_uri"),
            state.get("supplier_id"),
            filename=state.get("filename"),
            content_base64=state.get("content_base64"),
        )
        invoice = result["invoice"]
        return {
            "archived_source_uri": result["sourceUri"],
            "invoice": invoice,
            "status": "awaiting_confirmation" if invoice.get("status") == "EXTRACTED" else "reviewing",
            "final_reply": _extraction_summary(invoice),
        }

    def ask_for_review(state: InvoiceReviewState) -> dict[str, Any]:
        invoice = state["invoice"]
        response = interrupt(
            {
                "kind": "invoice_review",
                "message": "Corrige las líneas pendientes y reanuda el mismo thread.",
                "invoice": invoice,
                "reviewError": state.get("review_error"),
                "resumeSchema": {
                    "action": "apply | cancel",
                    "corrections": [{"lineIndex": 0, "unitsPerPack": "1", "packExpression": "1*1"}],
                },
            }
        )
        return {"review_response": _resume_mapping(response, "La revisión"), "review_error": None}

    async def apply_review(state: InvoiceReviewState) -> dict[str, Any]:
        response = state.get("review_response", {})
        if response.get("action") == "cancel":
            return {"status": "cancelled", "final_reply": "Revisión de factura cancelada por el empleado."}
        corrections = response.get("corrections")
        if not isinstance(corrections, list):
            return {"review_error": "Debes enviar una lista de corrections para continuar."}
        try:
            invoice = await workflow.revise(state["invoice"], corrections)
        except Exception as error:
            return {"review_error": str(error)}
        return {
            "invoice": invoice,
            "status": "awaiting_confirmation" if invoice.get("status") == "EXTRACTED" else "reviewing",
            "final_reply": _review_summary(invoice),
        }

    def ask_for_confirmation(state: InvoiceReviewState) -> dict[str, Any]:
        response = interrupt(
            {
                "kind": "invoice_import_confirmation",
                "message": "La factura está validada. ¿Quieres importarla al catálogo?",
                "invoice": state["invoice"],
                "resumeSchema": {"approved": True},
            }
        )
        return {"confirmation": _resume_mapping(response, "La confirmación")}

    async def import_invoice(state: InvoiceReviewState) -> dict[str, Any]:
        if state.get("confirmation", {}).get("approved") is not True:
            return {"status": "cancelled", "final_reply": "Importación cancelada; la factura sigue archivada."}
        result = await workflow.import_invoice(state["invoice"])
        return {
            "status": "imported",
            "import_result": result,
            "final_reply": f"Factura importada. Se añadieron {result.get('insertedOffers', 0)} ofertas.",
        }

    def after_extraction(state: InvoiceReviewState) -> str:
        return "confirm" if state.get("status") == "awaiting_confirmation" else "review"

    def after_review(state: InvoiceReviewState) -> str:
        if state.get("status") == "cancelled":
            return "end"
        return "confirm" if state.get("status") == "awaiting_confirmation" else "review"

    graph = StateGraph(InvoiceReviewState)
    graph.add_node("extract_document", extract_document)
    graph.add_node("request_review", ask_for_review)
    graph.add_node("apply_review", apply_review)
    graph.add_node("request_confirmation", ask_for_confirmation)
    graph.add_node("import_invoice", import_invoice)
    graph.add_edge(START, "extract_document")
    graph.add_conditional_edges(
        "extract_document",
        after_extraction,
        {"review": "request_review", "confirm": "request_confirmation"},
    )
    graph.add_edge("request_review", "apply_review")
    graph.add_conditional_edges(
        "apply_review",
        after_review,
        {"review": "request_review", "confirm": "request_confirmation", "end": END},
    )
    graph.add_edge("request_confirmation", "import_invoice")
    graph.add_edge("import_invoice", END)
    return graph.compile(checkpointer=checkpointer)


def _extraction_summary(invoice: Mapping[str, Any]) -> str:
    lines = invoice.get("lines", [])
    pending = sum(1 for line in lines if isinstance(line, Mapping) and line.get("validationStatus") != "VALID")
    return f"Factura extraída: {len(lines)} líneas; {pending} requieren revisión."


def _review_summary(invoice: Mapping[str, Any]) -> str:
    lines = invoice.get("lines", [])
    pending = sum(1 for line in lines if isinstance(line, Mapping) and line.get("validationStatus") != "VALID")
    return "Factura validada y lista para confirmar." if pending == 0 else f"Quedan {pending} líneas por revisar."


def _resume_mapping(response: Any, label: str) -> dict[str, Any]:
    """Normaliza el resume de Studio, que puede llegar como objeto o texto JSON."""
    if isinstance(response, Mapping):
        return dict(response)
    if isinstance(response, str):
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError as error:
            raise ValueError(f"{label} debe reanudarse con un objeto JSON válido.") from error
        if isinstance(parsed, Mapping):
            return dict(parsed)
    raise ValueError(f"{label} debe reanudarse con un objeto JSON.")
