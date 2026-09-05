from __future__ import annotations

from typing import Protocol

from supplier_bridge.domain import SupplierOfferSnapshot


class SupplierCatalogPort(Protocol):
    provider_id: str

    async def fetch_snapshot(self) -> SupplierOfferSnapshot: ...
