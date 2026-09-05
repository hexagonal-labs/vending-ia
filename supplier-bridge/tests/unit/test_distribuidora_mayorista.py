from decimal import Decimal

import pytest

from supplier_bridge.domain import SupplierCostPolicy
from supplier_bridge.infrastructure.distribuidora_mayorista import DistribuidoraMayoristaClient, apply_cost_policy


def policy(*, includes_vat: bool = False, includes_surcharge: bool = False) -> SupplierCostPolicy:
    return SupplierCostPolicy(
        price_includes_vat=includes_vat,
        price_includes_equivalence_surcharge=includes_surcharge,
        vat_rate=Decimal("0.21"),
        equivalence_surcharge_rate=Decimal("0.052"),
    )


def test_normalizes_unit_cost_with_explicit_vat_and_surcharge_policy() -> None:
    offer = DistribuidoraMayoristaClient.to_offer(
        {
            "id_product": 1101,
            "name": "Refresco cola lata 330 ml",
            "unit_price": "0,50 €",
            "availability": "available",
            "ean13": "8429359000509",
            "reference": "COLA-330",
        },
        policy(),
    )

    assert offer.unit_cost_with_tax_and_surcharge == Decimal("0.6310")
    assert offer.barcode == "8429359000509"
    assert offer.supplier_reference == "COLA-330"


def test_does_not_apply_vat_twice_when_api_price_already_includes_it() -> None:
    cost = apply_cost_policy(Decimal("0.50"), policy(includes_vat=True))

    assert cost == Decimal("0.5215")


def test_falls_back_to_box_price_divided_by_units_per_pack() -> None:
    offer = DistribuidoraMayoristaClient.to_offer(
        {
            "id_product": 1101,
            "name": "Refresco cola lata 330 ml 1x24",
            "price": "12,00 €",
            "unit_price_ratio": 24,
        },
        policy(includes_vat=True, includes_surcharge=True),
    )

    assert offer.unit_cost_with_tax_and_surcharge == Decimal("0.5000")


def test_requires_credentials_before_requesting_the_supplier() -> None:
    client = DistribuidoraMayoristaClient("https://example.test", "", "", "", policy())

    with pytest.raises(RuntimeError, match="DISTRIBUIDORA_MAYORISTA_EMAIL"):
        client._assert_configured()
