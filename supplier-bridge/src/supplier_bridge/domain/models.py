from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SupplierCostPolicy:
    price_includes_vat: bool
    price_includes_equivalence_surcharge: bool
    vat_rate: Decimal
    equivalence_surcharge_rate: Decimal


@dataclass(frozen=True, slots=True)
class SupplierOffer:
    supplier_product_id: str
    name: str
    unit_cost_with_tax_and_surcharge: Decimal
    available: bool
    barcode: str | None = None
    supplier_reference: str | None = None


@dataclass(frozen=True, slots=True)
class SupplierOfferSnapshot:
    provider_id: str
    retrieved_at: datetime
    products: tuple[SupplierOffer, ...]
