from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class NayaxMachine:
    machine_id: int
    name: str


@dataclass(frozen=True, slots=True)
class NayaxPrices:
    """Precios publicados por Nayax.

    ``machine`` es el PVP efectivo configurado en la máquina y es la única
    fuente válida para calcular márgenes. Los demás precios se conservan solo
    como información de catálogo.
    """

    machine: Decimal | None = None
    cash: Decimal | None = None


@dataclass(frozen=True, slots=True)
class NayaxProduct:
    machine_id: int
    machine_product_id: str
    name: str
    prices: NayaxPrices
    nayax_product_id: int | None = None
    ean: str | None = None


@dataclass(frozen=True, slots=True)
class SupplierProduct:
    id: str
    name: str
    unit_price: Decimal
    units_per_pack: Decimal
    box_price: Decimal
    available: bool
    provider_id: str = "distribuidora-mayorista"


@dataclass(frozen=True, slots=True)
class ProductMapping:
    nayax_product: str
    supplier_product_id: str
