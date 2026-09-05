from decimal import Decimal

from nayax_agents.domain import compute_margin


def test_compute_margin_marks_low_margin_and_target_price() -> None:
    result = compute_margin(Decimal("1.00"), Decimal("0.65"))

    assert result.margin == Decimal("0.35")
    assert result.below_threshold is True
    assert result.target_price == Decimal("1.3")


def test_compute_margin_rejects_zero_sale_price() -> None:
    try:
        compute_margin(Decimal("0"), Decimal("0.65"))
    except ValueError as error:
        assert "mayor que cero" in str(error)
    else:
        raise AssertionError("Se esperaba ValueError")
