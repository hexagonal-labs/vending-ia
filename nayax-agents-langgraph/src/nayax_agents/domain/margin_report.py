from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import NayaxProduct, ProductMapping, SupplierProduct
from .pricing import compute_margin


@dataclass(frozen=True, slots=True)
class MarginRow:
    machine_name: str
    nayax_name: str
    machine_price: Decimal
    supplier: SupplierProduct
    margin: Decimal
    below_threshold: bool
    target_price: Decimal


@dataclass(frozen=True, slots=True)
class MatchMarginsInput:
    nayax_products: Sequence[NayaxProduct]
    machine_name_by_id: Mapping[int, str]
    supplier_products: Sequence[SupplierProduct]
    mappings: Sequence[ProductMapping]


@dataclass(frozen=True, slots=True)
class MatchMarginsResult:
    rows: Sequence[MarginRow]
    unavailable: Sequence[str]
    unmapped: Sequence[str]
    missing_machine_price: Sequence[str]


def match_and_compute_margins(input_data: MatchMarginsInput) -> MatchMarginsResult:
    supplier_by_id = {product.id: product for product in input_data.supplier_products}
    mapping_by_name = {mapping.nayax_product: mapping for mapping in input_data.mappings}
    rows: list[MarginRow] = []
    unavailable: list[str] = []
    unmapped: list[str] = []
    missing_machine_price: list[str] = []
    seen_unmapped: set[str] = set()
    seen_missing_machine_price: set[str] = set()

    for product in input_data.nayax_products:
        machine_price = product.prices.machine
        if machine_price is None:
            if product.name not in seen_missing_machine_price:
                missing_machine_price.append(product.name)
                seen_missing_machine_price.add(product.name)
            continue

        mapping = mapping_by_name.get(product.name)
        if mapping is None:
            if product.name not in seen_unmapped:
                unmapped.append(product.name)
                seen_unmapped.add(product.name)
            continue

        supplier = supplier_by_id.get(mapping.supplier_product_id)
        if supplier is None:
            name = f"{product.name} (id de proveedor {mapping.supplier_product_id} no encontrado en el catalogo)"
            if name not in seen_unmapped:
                unmapped.append(name)
                seen_unmapped.add(name)
            continue

        if not supplier.available:
            unavailable.append(f"{product.name} ({supplier.name})")
            continue

        calculation = compute_margin(machine_price, supplier.unit_price)
        rows.append(
            MarginRow(
                machine_name=input_data.machine_name_by_id.get(product.machine_id, str(product.machine_id)),
                nayax_name=product.name,
                machine_price=machine_price,
                supplier=supplier,
                margin=calculation.margin,
                below_threshold=calculation.below_threshold,
                target_price=calculation.target_price,
            )
        )

    return MatchMarginsResult(
        rows=rows,
        unavailable=unavailable,
        unmapped=unmapped,
        missing_machine_price=missing_machine_price,
    )


def format_euro(value: Decimal) -> str:
    return f"{value:.2f}€"


def build_margin_report_text(result: MatchMarginsResult, reference_date: date | None = None) -> str:
    report_date = reference_date or date.today()
    lines = [f"Informe de margenes - {report_date.strftime('%d/%m/%Y')}"]
    low = [row for row in result.rows if row.below_threshold]
    good = [row for row in result.rows if not row.below_threshold]

    if low:
        lines.extend(["", "MARGEN POR DEBAJO DEL 50%:"])
        lines.extend(
            f"- [{row.machine_name}] {row.nayax_name}: PVP de máquina {format_euro(row.machine_price)} "
            f"vs coste {format_euro(row.supplier.unit_price)} ({row.supplier.name}) -> "
            f"margen {row.margin * 100:.0f}% (sube a {format_euro(row.target_price)} para el 50%)"
            for row in low
        )

    if good:
        lines.extend(["", "MARGEN OK:"])
        lines.extend(f"- [{row.machine_name}] {row.nayax_name}: margen {row.margin * 100:.0f}%" for row in good)

    if result.unavailable:
        lines.extend(["", "SIN STOCK EN EL PROVEEDOR (no se pudo calcular):"])
        lines.extend(f"- {name}" for name in result.unavailable)

    if result.unmapped:
        lines.extend(["", "SIN MAPEAR EN config/product-suppliers.yaml:"])
        lines.extend(f"- {name}" for name in result.unmapped)

    if result.missing_machine_price:
        lines.extend(["", "SIN MACHINEPRICE EN NAYAX (no se pudo calcular):"])
        lines.extend(f"- {name}" for name in result.missing_machine_price)

    if not low and not good:
        lines.extend(["", "No hay productos mapeados con precio de venta y de proveedor disponibles."])

    return "\n".join(lines)
