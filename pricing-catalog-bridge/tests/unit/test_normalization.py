from decimal import Decimal

from pricing_catalog_bridge.matching import normalize_ean, normalize_product_name


def test_normalizes_accents_content_and_pack_expressions() -> None:
    product = normalize_product_name("COCA COLA LATA 0,33 L 1*24")

    assert product.tokens == frozenset({"coca", "cola"})
    assert product.content_value == Decimal("330")
    assert product.content_unit == "ml"
    assert product.format == "lata"


def test_ean_is_only_usable_with_a_valid_length() -> None:
    assert normalize_ean("84 29359 00050 9") == "8429359000509"
    assert normalize_ean("no-ean") is None
