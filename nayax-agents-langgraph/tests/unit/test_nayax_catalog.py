import json
from decimal import Decimal
from typing import Any

import pytest

from nayax_agents.infrastructure.nayax_catalog import McpNayaxCatalog


class FakeTool:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    async def ainvoke(self, arguments: dict[str, Any]) -> Any:
        return self.payload


@pytest.mark.asyncio
async def test_mcp_catalog_maps_structured_tool_results() -> None:
    catalog = McpNayaxCatalog(
        {
            "list_machines": FakeTool(json.dumps({"machines": [{"machineId": 5001, "name": "Mock"}]})),
            "list_machine_products": FakeTool(
                [
                    {
                        "text": json.dumps(
                            {
                                "contractVersion": "nayax-machine-products/v1",
                                "machineId": 5001,
                                "products": [
                                    {
                                        "machineId": 5001,
                                        "machineProductId": "3",
                                        "name": "DEX vacio o nombre antiguo",
                                        "nayaxProductId": 1101,
                                        "catalogProduct": {
                                            "productName": "Agua mineral 50 cl",
                                            "eanCode": "0000000000000",
                                        },
                                        "prices": {"machine": "1.80", "cash": "1.00"},
                                    }
                                ]
                            }
                        )
                    }
                ]
            ),
        }
    )

    machines = await catalog.list_machines()
    products = await catalog.list_machine_products(5001)

    assert machines[0].machine_id == 5001
    assert products[0].machine_product_id == "3"
    assert products[0].name == "Agua mineral 50 cl"
    assert products[0].prices.machine == Decimal("1.80")
    assert products[0].prices.cash == Decimal("1.00")
    assert products[0].nayax_product_id == 1101
    assert products[0].ean == "0000000000000"
