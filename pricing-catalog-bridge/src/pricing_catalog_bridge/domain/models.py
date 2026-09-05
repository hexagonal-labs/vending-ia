from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal


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
    observed_at: datetime
    offers: tuple[SupplierOffer, ...]


@dataclass(frozen=True, slots=True)
class IngestionResult:
    provider_id: str
    import_id: str
    source_hash: str
    ingested_at: datetime
    inserted_offers: int
    duplicate: bool
    catalog_path: str


@dataclass(frozen=True, slots=True)
class VendingProduct:
    canonical_product_id: str
    product_name: str
    ean: str | None = None


MatchStatus = Literal[
    "MATCHED_EXACT",
    "MATCHED_CONFIRMED",
    "PENDING_REVIEW",
    "UNMATCHED",
    "SOURCE_INCOMPLETE",
]
MatchMethod = Literal["ean", "sku", "confirmed_mapping", "normalized_attributes", "fuzzy", "none"]


@dataclass(frozen=True, slots=True)
class MatchCandidate:
    supplier_product_id: str
    name: str
    confidence: float
    reason: str


@dataclass(frozen=True, slots=True)
class ProductMatch:
    canonical_product_id: str
    supplier_product_id: str | None
    status: MatchStatus
    method: MatchMethod
    confidence: float
    alternatives: tuple[MatchCandidate, ...]
    reason: str
    review_id: str | None = None
