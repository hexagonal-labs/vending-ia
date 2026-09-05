from decimal import Decimal

from pricing_catalog_bridge.domain import SupplierOffer, VendingProduct
from pricing_catalog_bridge.matching import ProductMatcher


def test_matches_unique_ean_before_names() -> None:
    result = ProductMatcher().match(
        VendingProduct("nayax:1101", "Nombre de Nayax", "8429359000509"),
        (SupplierOffer("cola", "Nombre totalmente distinto", Decimal("0.62"), True, "8429359000509"),),
        {},
    )

    assert result.status == "MATCHED_EXACT"
    assert result.method == "ean"
    assert result.supplier_product_id == "cola"


def test_matches_normalized_names_when_content_and_format_match() -> None:
    result = ProductMatcher().match(
        VendingProduct("nayax:1101", "Coca Cola Lata 330 ML"),
        (SupplierOffer("cola", "COCA-COLA LATA 0,33 L 1*24", Decimal("0.62"), True),),
        {},
    )

    assert result.status == "MATCHED_EXACT"
    assert result.method == "normalized_attributes"


def test_different_product_size_is_never_matched_automatically() -> None:
    result = ProductMatcher().match(
        VendingProduct("nayax:1101", "Pringles Original 40 g"),
        (SupplierOffer("pringles-70", "Pringles Original 70 g", Decimal("0.90"), True),),
        {},
    )

    assert result.status == "UNMATCHED"
    assert result.confidence == 0.0
    assert "tamaño" in result.reason


def test_ambiguous_fuzzy_name_creates_a_review_candidate() -> None:
    result = ProductMatcher().match(
        VendingProduct("nayax:1101", "Coca Cola Zero Lata 330 ML"),
        (SupplierOffer("cola-zero", "Coca Cola Zero Azucar Lata 330 ML", Decimal("0.62"), True),),
        {},
    )

    assert result.status == "PENDING_REVIEW"
    assert result.method == "fuzzy"
    assert 0.75 <= result.confidence < 0.95


def test_confirmed_mapping_overrides_name_matching() -> None:
    result = ProductMatcher().match(
        VendingProduct("nayax:1101", "Nombre que cambió"),
        (SupplierOffer("cola", "Descripción de proveedor", Decimal("0.62"), True),),
        {"nayax:1101": "cola"},
    )

    assert result.status == "MATCHED_CONFIRMED"
    assert result.method == "confirmed_mapping"
