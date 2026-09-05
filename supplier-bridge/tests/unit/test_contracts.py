from datetime import UTC, datetime
from decimal import Decimal

from supplier_bridge.application.contracts import CostPolicyV1, SupplierOfferSnapshotV1
from supplier_bridge.domain import SupplierCostPolicy, SupplierOffer, SupplierOfferSnapshot


def test_snapshot_contract_matches_pricing_catalog_contract_shape() -> None:
    snapshot = SupplierOfferSnapshot(
        provider_id="distribuidora-mayorista",
        retrieved_at=datetime(2026, 9, 4, 10, 0, tzinfo=UTC),
        products=(SupplierOffer("1101", "Refresco cola", Decimal("0.6310"), True, "8429359000509"),),
    )

    payload = SupplierOfferSnapshotV1.from_domain(snapshot).model_dump(mode="json", by_alias=True)

    assert payload["contractVersion"] == "supplier-offer-snapshot/v1"
    assert payload["products"][0]["unitCostWithTaxAndSurcharge"] == "0.6310"


def test_cost_policy_contract_exposes_tax_assumptions() -> None:
    payload = CostPolicyV1.from_domain(
        SupplierCostPolicy(False, False, Decimal("0.21"), Decimal("0.052"))
    ).model_dump(mode="json", by_alias=True)

    assert payload == {
        "priceIncludesVat": False,
        "priceIncludesEquivalenceSurcharge": False,
        "vatRate": "0.21",
        "equivalenceSurchargeRate": "0.052",
    }
