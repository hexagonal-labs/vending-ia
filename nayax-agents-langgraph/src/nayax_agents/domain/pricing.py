from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

MARGIN_THRESHOLD = Decimal("0.50")


@dataclass(frozen=True, slots=True)
class MarginCalculation:
    margin: Decimal
    below_threshold: bool
    target_price: Decimal


def compute_margin(machine_price: Decimal, supplier_unit_price: Decimal) -> MarginCalculation:
    """Calcula margen bruto usando el PVP ``MachinePrice`` de Nayax."""
    if machine_price <= 0:
        raise ValueError("El precio de venta debe ser mayor que cero")
    margin = (machine_price - supplier_unit_price) / machine_price
    return MarginCalculation(
        margin=margin,
        below_threshold=margin < MARGIN_THRESHOLD,
        target_price=supplier_unit_price / (1 - MARGIN_THRESHOLD),
    )
