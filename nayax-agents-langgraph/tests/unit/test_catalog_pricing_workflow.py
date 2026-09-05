from __future__ import annotations

from typing import Any

import pytest

from nayax_agents.application.catalog_pricing_workflow import CatalogPricingWorkflow, _mapping


class StubTool:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def ainvoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(arguments)
        return self.response


@pytest.mark.asyncio
async def test_catalog_source_compares_existing_invoice_catalog_without_supplier_api() -> None:
    list_machines = StubTool({"machines": [{"machineId": 5001, "name": "Máquina prueba"}]})
    list_products = StubTool(
        {
            "contractVersion": "nayax-machine-products/v1",
            "machineId": 5001,
            "products": [
                {
                    "machineProductId": "1",
                    "machineId": 5001,
                    "nayaxProductId": 1101,
                    "name": "Nombre DEX vacío",
                    "catalogProduct": {"productName": "COCA COLA LATA 330 ML", "eanCode": "5740600997656"},
                    "prices": {"machine": "1.80"},
                }
            ],
        }
    )
    supplier_api = StubTool({"snapshot": {}})
    match_products = StubTool(
        {
            "matches": [
                {
                    "canonicalProductId": "nayax:1101",
                    "supplierProductId": "invoice-ref:5740600989330",
                    "status": "MATCHED_EAN",
                    "method": "ean",
                    "confidence": 1.0,
                    "reason": "EAN coincidente.",
                }
            ]
        }
    )
    report = StubTool({"reportPath": "/reports/cashoreca/machine.xlsx"})
    workflow = CatalogPricingWorkflow(
        {"list_machines": list_machines, "list_machine_products": list_products},
        {"fetch_supplier_offers": supplier_api},
        {"match_products": match_products, "generate_machine_supplier_report": report},
    )

    result = await workflow.run("cashoreca", provider_source="catalog")

    assert result["providerSource"] == "catalog"
    assert result["reports"] == ["/reports/cashoreca/machine.xlsx"]
    assert supplier_api.calls == []
    assert match_products.calls[0]["provider_id"] == "cashoreca"
    assert report.calls[0]["machine_products"][0]["productName"] == "COCA COLA LATA 330 ML"
    assert report.calls[0]["machine_products"][0]["machinePrice"] == "1.80"


@pytest.mark.asyncio
async def test_all_catalogs_compares_each_provider_with_current_catalog() -> None:
    list_machines = StubTool({"machines": [{"machineId": 5001, "name": "Máquina prueba"}]})
    list_products = StubTool(
        {
            "contractVersion": "nayax-machine-products/v1",
            "machineId": 5001,
            "products": [
                {
                    "machineProductId": "1",
                    "machineId": 5001,
                    "nayaxProductId": 1101,
                    "name": "Producto prueba",
                    "prices": {"machine": "1.80"},
                }
            ],
        }
    )
    list_providers = StubTool({"providerIds": ["cashoreca", "distribuidora-mayorista"]})
    match_products = StubTool({"matches": []})
    report = StubTool({"reportPath": "/reports/provider/machine.xlsx"})
    workflow = CatalogPricingWorkflow(
        {"list_machines": list_machines, "list_machine_products": list_products},
        {"fetch_supplier_offers": StubTool({"snapshot": {}})},
        {
            "list_catalog_providers": list_providers,
            "match_products": match_products,
            "generate_machine_supplier_report": report,
        },
    )

    result = await workflow.run_all_catalogs()

    assert result["providerCount"] == 2
    assert [item["supplierId"] for item in result["providers"]] == ["cashoreca", "distribuidora-mayorista"]
    assert [call["provider_id"] for call in match_products.calls] == ["cashoreca", "distribuidora-mayorista"]
    assert len(result["reports"]) == 2


def test_empty_mcp_tool_response_exposes_a_useful_error() -> None:
    with pytest.raises(RuntimeError, match="respuesta vacía"):
        _mapping([])
