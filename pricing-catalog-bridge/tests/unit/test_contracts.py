from decimal import Decimal

import pytest
from pydantic import ValidationError

from pricing_catalog_bridge.application.contracts import MatchProductsRequestV1, SupplierOfferSnapshotV1


def test_snapshot_contract_uses_decimal_and_maps_to_domain() -> None:
    contract = SupplierOfferSnapshotV1.model_validate(
        {
            "contractVersion": "supplier-offer-snapshot/v1",
            "providerId": "cashoreca",
            "retrievedAt": "2026-09-04T10:00:00Z",
            "products": [
                {
                    "supplierProductId": "cola-330",
                    "name": "Refresco cola lata 330 ml",
                    "unitCostWithTaxAndSurcharge": "0.62",
                    "available": True,
                }
            ],
        }
    )

    snapshot = contract.to_domain()
    assert snapshot.offers[0].unit_cost_with_tax_and_surcharge == Decimal("0.62")


def test_snapshot_contract_rejects_unknown_or_incomplete_data() -> None:
    with pytest.raises(ValidationError):
        SupplierOfferSnapshotV1.model_validate(
            {
                "contractVersion": "supplier-offer-snapshot/v1",
                "providerId": "cashoreca",
                "retrievedAt": "2026-09-04T10:00:00Z",
                "products": [{"supplierProductId": "cola-330", "name": "Cola", "available": True}],
            }
        )


def test_snapshot_contract_requires_safe_provider_id_and_timezone() -> None:
    with pytest.raises(ValidationError):
        SupplierOfferSnapshotV1.model_validate(
            {
                "contractVersion": "supplier-offer-snapshot/v1",
                "providerId": "../cashoreca",
                "retrievedAt": "2026-09-04T10:00:00",
                "products": [],
            }
        )


def test_matching_contract_requires_canonical_nayax_ids_and_audit_fields() -> None:
    request = MatchProductsRequestV1.model_validate(
        {
            "providerId": "cashoreca",
            "runId": "pricing-20260904-001",
            "idempotencyKey": "pricing-20260904-001:cashoreca",
            "vendingProducts": [
                {
                    "canonicalProductId": "nayax:1101",
                    "productName": "Coca Cola Lata 330 ml",
                    "ean": "8429359000509",
                }
            ],
        }
    )

    assert request.vending_products[0].to_domain().canonical_product_id == "nayax:1101"
