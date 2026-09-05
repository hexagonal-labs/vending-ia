from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from supplier_bridge.domain import SupplierCostPolicy, SupplierOffer, SupplierOfferSnapshot

SUPPLIER_OFFER_SNAPSHOT_CONTRACT_VERSION = "supplier-offer-snapshot/v1"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SupplierOfferV1(ContractModel):
    supplier_product_id: str = Field(alias="supplierProductId")
    name: str
    unit_cost_with_tax_and_surcharge: Decimal = Field(alias="unitCostWithTaxAndSurcharge")
    available: bool
    barcode: str | None = None
    supplier_reference: str | None = Field(default=None, alias="supplierReference")

    @classmethod
    def from_domain(cls, offer: SupplierOffer) -> SupplierOfferV1:
        return cls(
            supplierProductId=offer.supplier_product_id,
            name=offer.name,
            unitCostWithTaxAndSurcharge=offer.unit_cost_with_tax_and_surcharge,
            available=offer.available,
            barcode=offer.barcode,
            supplierReference=offer.supplier_reference,
        )


class SupplierOfferSnapshotV1(ContractModel):
    contract_version: Literal["supplier-offer-snapshot/v1"] = Field(
        default="supplier-offer-snapshot/v1", alias="contractVersion"
    )
    provider_id: str = Field(alias="providerId")
    retrieved_at: datetime = Field(alias="retrievedAt")
    products: list[SupplierOfferV1]

    @classmethod
    def from_domain(cls, snapshot: SupplierOfferSnapshot) -> SupplierOfferSnapshotV1:
        return cls(
            providerId=snapshot.provider_id,
            retrievedAt=snapshot.retrieved_at,
            products=[SupplierOfferV1.from_domain(product) for product in snapshot.products],
        )


class CostPolicyV1(ContractModel):
    price_includes_vat: bool = Field(alias="priceIncludesVat")
    price_includes_equivalence_surcharge: bool = Field(alias="priceIncludesEquivalenceSurcharge")
    vat_rate: Decimal = Field(alias="vatRate")
    equivalence_surcharge_rate: Decimal = Field(alias="equivalenceSurchargeRate")

    @classmethod
    def from_domain(cls, policy: SupplierCostPolicy) -> CostPolicyV1:
        return cls(
            priceIncludesVat=policy.price_includes_vat,
            priceIncludesEquivalenceSurcharge=policy.price_includes_equivalence_surcharge,
            vatRate=policy.vat_rate,
            equivalenceSurchargeRate=policy.equivalence_surcharge_rate,
        )
