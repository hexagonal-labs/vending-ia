import json
from decimal import Decimal
from pathlib import Path

from nayax_agents.application.contracts import (
    NayaxMachineProductsResponseV1,
    SupplierInvoiceIngestionV1,
    SupplierOfferSnapshotV1,
)

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"


def _fixture(name: str) -> object:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_nayax_machine_products_v1_fixture_keeps_machine_price_and_catalog_name() -> None:
    response = NayaxMachineProductsResponseV1.model_validate(_fixture("nayax_machine_products_v1.json"))

    product = response.products[0]
    assert product.prices.machine == Decimal("1.80")
    assert product.catalog_product is not None
    assert product.catalog_product.product_name == "Refresco cola lata 330 ml"


def test_supplier_fixtures_validate_future_bridge_contracts() -> None:
    offer = SupplierOfferSnapshotV1.model_validate(_fixture("supplier_offer_snapshot_v1.json"))
    invoice = SupplierInvoiceIngestionV1.model_validate(_fixture("cashoreca_invoice_ingestion_v1.json"))

    assert offer.products[0].unit_cost_with_tax_and_surcharge == Decimal("0.62")
    assert invoice.lines[0].pack_expression == "1*24"
    assert invoice.lines[0].line_total_net == Decimal("21.02")
