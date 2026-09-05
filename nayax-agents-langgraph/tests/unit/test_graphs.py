import asyncio
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from nayax_agents.domain import NayaxMachine, NayaxPrices, NayaxProduct, ProductMapping, SupplierProduct
from nayax_agents.graphs.info_graph import build_info_graph
from nayax_agents.graphs.pricing_graph import (
    PricingGraphDependencies,
    _list_machine_products_limited,
    build_pricing_graph,
)
from nayax_agents.infrastructure.checkpointer import open_sqlite_checkpointer


class FakeInfoModel:
    def bind_tools(self, tools: list[Any]) -> "FakeInfoModel":
        return self

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        return AIMessage(content="Respuesta de prueba")


class FakePricingModel:
    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        return AIMessage(content="Informe redactado de prueba")


class FakeCatalog:
    async def list_machines(self) -> list[NayaxMachine]:
        return [NayaxMachine(5001, "Mock")]

    async def list_machine_products(self, machine_id: int) -> list[NayaxProduct]:
        return [NayaxProduct(5001, "1", "Kit Kat", NayaxPrices(machine=Decimal("1.00")))]


class FakeSupplier:
    async def fetch_products(self) -> list[SupplierProduct]:
        return [SupplierProduct("kit", "Kit Kat proveedor", Decimal("0.65"), Decimal("24"), Decimal("15.60"), True)]


@pytest.mark.asyncio
async def test_info_graph_returns_model_message() -> None:
    graph = build_info_graph(FakeInfoModel(), [])

    result = await graph.ainvoke({"messages": [{"role": "user", "content": "hola"}]})

    assert result["messages"][-1].content == "Respuesta de prueba"


@pytest.mark.asyncio
async def test_pricing_graph_calculates_domain_and_persists_checkpoint(tmp_path: Path) -> None:
    dependencies = PricingGraphDependencies(
        FakeCatalog(),
        FakeSupplier(),
        [ProductMapping("Kit Kat", "kit")],
        FakePricingModel(),
    )

    async with open_sqlite_checkpointer(tmp_path / "checkpoints.db") as checkpointer:
        graph = build_pricing_graph(dependencies, checkpointer)
        result = await graph.ainvoke(
            {"status": "running"},
            config={"configurable": {"thread_id": "pricing-test"}},
        )

        assert result["margin_result"].rows[0].below_threshold is True
        assert result["final_reply"] == "Informe redactado de prueba"
        snapshot = await graph.aget_state({"configurable": {"thread_id": "pricing-test"}})

    assert snapshot.values["status"] == "completed"


@pytest.mark.asyncio
async def test_machine_product_fetches_respect_configured_concurrency() -> None:
    class ConcurrentCatalog:
        def __init__(self) -> None:
            self.active = 0
            self.peak = 0

        async def list_machine_products(self, machine_id: int) -> list[NayaxProduct]:
            self.active += 1
            self.peak = max(self.peak, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            return []

    catalog = ConcurrentCatalog()
    machines = [NayaxMachine(machine_id, f"Máquina {machine_id}") for machine_id in range(1, 8)]

    batches = await _list_machine_products_limited(catalog, machines, max_concurrency=2)

    assert batches == [[] for _ in machines]
    assert catalog.peak == 2
