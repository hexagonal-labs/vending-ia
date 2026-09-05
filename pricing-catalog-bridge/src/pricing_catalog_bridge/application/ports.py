from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pricing_catalog_bridge.domain import IngestionResult, ProductMatch, SupplierOfferSnapshot, VendingProduct


class PricingCatalogPort(Protocol):
    def initialize(self) -> None: ...

    def record_supplier_snapshot(
        self, snapshot: SupplierOfferSnapshot, idempotency_key: str
    ) -> IngestionResult: ...

    def catalog_path_for(self, provider_id: str) -> Path: ...

    def match_products(
        self,
        provider_id: str,
        vending_products: tuple[VendingProduct, ...],
        *,
        run_id: str,
        idempotency_key: str,
    ) -> tuple[ProductMatch, ...]: ...
