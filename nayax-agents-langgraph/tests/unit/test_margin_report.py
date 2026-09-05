from datetime import date
from decimal import Decimal

from nayax_agents.domain import (
    MatchMarginsInput,
    NayaxPrices,
    NayaxProduct,
    ProductMapping,
    SupplierProduct,
    build_margin_report_text,
    match_and_compute_margins,
)


def test_match_and_compute_margins_separates_low_good_unavailable_and_unmapped() -> None:
    result = match_and_compute_margins(
        MatchMarginsInput(
            nayax_products=[
                NayaxProduct(5001, "1", "Kit Kat", NayaxPrices(machine=Decimal("1.00"))),
                NayaxProduct(5001, "2", "Lacasitos", NayaxPrices(machine=Decimal("1.50"))),
                NayaxProduct(5001, "3", "Sin stock", NayaxPrices(machine=Decimal("1.00"))),
                NayaxProduct(5001, "4", "Sin mapping", NayaxPrices(machine=Decimal("1.00"))),
                NayaxProduct(5001, "5", "Sin MachinePrice", NayaxPrices(cash=Decimal("1.00"))),
            ],
            machine_name_by_id={5001: "Vending Chuches"},
            supplier_products=[
                SupplierProduct(
                    "kit", "Kit Kat proveedor", Decimal("0.65"), Decimal("24"), Decimal("15.60"), True
                ),
                SupplierProduct(
                    "lacasitos", "Lacasitos proveedor", Decimal("0.60"), Decimal("20"), Decimal("12.00"), True
                ),
                SupplierProduct(
                    "stock", "Sin stock proveedor", Decimal("0.50"), Decimal("20"), Decimal("10.00"), False
                ),
            ],
            mappings=[
                ProductMapping("Kit Kat", "kit"),
                ProductMapping("Lacasitos", "lacasitos"),
                ProductMapping("Sin stock", "stock"),
            ],
        )
    )

    assert len(result.rows) == 2
    assert result.rows[0].below_threshold is True
    assert result.rows[1].below_threshold is False
    assert result.unavailable == ["Sin stock (Sin stock proveedor)"]
    assert result.unmapped == ["Sin mapping"]
    assert result.missing_machine_price == ["Sin MachinePrice"]


def test_margin_report_has_expected_sections() -> None:
    result = match_and_compute_margins(
        MatchMarginsInput(
            nayax_products=[NayaxProduct(5001, "1", "Kit Kat", NayaxPrices(machine=Decimal("1.00")))],
            machine_name_by_id={5001: "Vending Chuches"},
            supplier_products=[
                SupplierProduct(
                    "kit", "Kit Kat proveedor", Decimal("0.65"), Decimal("24"), Decimal("15.60"), True
                )
            ],
            mappings=[ProductMapping("Kit Kat", "kit")],
        )
    )

    text = build_margin_report_text(result, date(2026, 1, 2))

    assert "Informe de margenes - 02/01/2026" in text
    assert "MARGEN POR DEBAJO DEL 50%" in text
    assert "Kit Kat" in text
    assert "PVP de máquina 1.00€" in text
