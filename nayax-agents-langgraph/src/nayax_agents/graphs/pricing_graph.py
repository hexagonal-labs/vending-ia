from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from nayax_agents.application.catalog_pricing_workflow import CatalogPricingWorkflow
from nayax_agents.domain import MatchMarginsInput, build_margin_report_text, match_and_compute_margins
from nayax_agents.graphs.state import NayaxGraphState
from nayax_agents.infrastructure.messages import message_content_text

PRICING_PROMPT = (Path(__file__).parents[1] / "prompts" / "pricing_agent.md").read_text(encoding="utf-8")


class CatalogPricingState(TypedDict, total=False):
    status: str
    final_reply: str
    pricing_result: dict[str, Any]
    supplier_id: str
    provider_source: str


class PricingGraphDependencies:
    def __init__(
        self,
        nayax_catalog: Any,
        supplier_catalog: Any,
        mappings: Sequence[Any],
        model: Any,
        *,
        max_machine_fetch_concurrency: int = 4,
    ) -> None:
        if max_machine_fetch_concurrency < 1:
            raise ValueError("max_machine_fetch_concurrency debe ser mayor que cero")
        self.nayax_catalog = nayax_catalog
        self.supplier_catalog = supplier_catalog
        self.mappings = mappings
        self.model = model
        self.max_machine_fetch_concurrency = max_machine_fetch_concurrency


async def _list_machine_products_limited(
    catalog: Any, machines: Sequence[Any], max_concurrency: int
) -> list[list[Any]]:
    """Obtiene productos sin sobrecargar Nayax y conservando el orden de máquinas."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def fetch(machine: Any) -> list[Any]:
        async with semaphore:
            return cast(list[Any], await catalog.list_machine_products(machine.machine_id))

    return cast(list[list[Any]], await asyncio.gather(*(fetch(machine) for machine in machines)))


def build_pricing_graph(dependencies: PricingGraphDependencies, checkpointer: Any = None) -> Any:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langgraph.graph import END, START, StateGraph

    async def collect_data(state: NayaxGraphState) -> dict[str, Any]:
        machines, supplier_products = await asyncio.gather(
            dependencies.nayax_catalog.list_machines(),
            dependencies.supplier_catalog.fetch_products(),
        )
        product_batches = await _list_machine_products_limited(
            dependencies.nayax_catalog,
            machines,
            dependencies.max_machine_fetch_concurrency,
        )
        products = [product for batch in product_batches for product in batch]
        return {
            "machines": machines,
            "nayax_products": products,
            "supplier_products": supplier_products,
            "mappings": dependencies.mappings,
            "status": "running",
        }

    def calculate(state: NayaxGraphState) -> dict[str, Any]:
        machines = state["machines"]
        result = match_and_compute_margins(
            MatchMarginsInput(
                nayax_products=state["nayax_products"],
                machine_name_by_id={machine.machine_id: machine.name for machine in machines},
                supplier_products=state["supplier_products"],
                mappings=state["mappings"],
            )
        )
        return {"margin_result": result, "raw_report": build_margin_report_text(result)}

    async def redact(state: NayaxGraphState) -> dict[str, str]:
        try:
            response = await dependencies.model.ainvoke(
                [SystemMessage(content=PRICING_PROMPT), HumanMessage(content=state["raw_report"])]
            )
            content = message_content_text(response).strip()
            return {"final_reply": content or state["raw_report"], "status": "completed"}
        except Exception:
            return {"final_reply": state["raw_report"], "status": "completed"}

    graph = StateGraph(NayaxGraphState)
    graph.add_node("collect_data", collect_data)
    graph.add_node("calculate", calculate)
    graph.add_node("redact", redact)
    graph.add_edge(START, "collect_data")
    graph.add_edge("collect_data", "calculate")
    graph.add_edge("calculate", "redact")
    graph.add_edge("redact", END)
    return graph.compile(checkpointer=checkpointer)


def build_catalog_pricing_graph(
    workflow: CatalogPricingWorkflow,
    checkpointer: Any = None,
    *,
    default_supplier_id: str = "distribuidora-mayorista",
    default_provider_source: str = "api",
) -> Any:
    """Grafo de Studio para el pricing nuevo, basado en bridges MCP aislados."""
    from langgraph.graph import END, START, StateGraph

    async def execute(state: CatalogPricingState) -> CatalogPricingState:
        supplier_id = str(state.get("supplier_id", default_supplier_id))
        provider_source = str(state.get("provider_source", default_provider_source))
        if provider_source not in {"api", "catalog"}:
            raise ValueError("provider_source debe ser 'api' o 'catalog'")
        result = await workflow.run(
            supplier_id,
            provider_source=cast(Literal["api", "catalog"], provider_source),
        )
        return {"status": "completed", "final_reply": str(result), "pricing_result": result}

    graph = StateGraph(CatalogPricingState)
    graph.add_node("execute_catalog_pricing", execute)
    graph.add_edge(START, "execute_catalog_pricing")
    graph.add_edge("execute_catalog_pricing", END)
    return graph.compile(checkpointer=checkpointer)
