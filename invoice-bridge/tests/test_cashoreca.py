from decimal import Decimal
from pathlib import Path

from pytest import MonkeyPatch, raises

from invoice_bridge import core
from invoice_bridge.core import extract, parse_cashoreca
from invoice_bridge.vision import VisionInvoice


def test_cashoreca_pack_and_discount_validation() -> None:
    line = parse_cashoreca("574|8429|COCA COLA LATA 330 ML 1*24|2|10.51|0|21.02|21")[0]

    assert line.units_per_pack == Decimal("24")
    assert line.pack_price_net == Decimal("10.51")
    assert line.validation_status == "VALID"


def test_archive_source_is_idempotent_and_owned_by_invoice_bridge(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    document = tmp_path / "a name.pdf"
    document.write_bytes(b"invoice-original")
    monkeypatch.setenv("INVOICE_DATA_DIR", str(tmp_path / "invoice-bridge-data"))

    first = core.archive_source(str(document))
    second = core.archive_source(str(document))

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    archive = Path(str(first["sourceUri"]))
    assert archive.parent == tmp_path / "invoice-bridge-data" / "uploads"
    assert archive.read_bytes() == b"invoice-original"


def test_invalid_total_requires_review() -> None:
    line = parse_cashoreca("574|8429|COCA COLA LATA 330 ML 1*24|2|10.51|0|20.00|21")[0]

    assert line.validation_status == "REVIEW_REQUIRED"


def test_cashoreca_plain_text_parses_table_without_pipe_separators() -> None:
    text = "5740600989330 5740600997656 COCA COLA LATA 330ML 1MP ETIQ 1*24 2 10.51 0 21.02 21%"

    line = parse_cashoreca(text)[0]

    assert line.supplier_reference == "5740600989330"
    assert line.barcode == "5740600997656"
    assert line.units_per_pack == Decimal("24")
    assert line.validation_status == "VALID"


def test_cashoreca_accepts_plus_in_a_pack_expression() -> None:
    line = parse_cashoreca("574|8429|AGUA FUENTE PRIMAVERA 50CL 1+24|2|4.81|0|9.62|10")[0]

    assert line.pack_expression == "1*24"
    assert line.units_per_pack == Decimal("24")
    assert line.validation_status == "VALID"


def test_cashoreca_recognizes_weight_followed_by_pack_count() -> None:
    line = parse_cashoreca("22049|8411276203644|PATATA EL GALLO JAMON 40G*14|2|6.32|0|12.64|10")[0]

    assert line.pack_expression == "40G*14"
    assert line.units_per_pack == Decimal("14")
    assert line.validation_status == "VALID"


def test_scanned_cashoreca_uses_vision(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    document = tmp_path / "cashoreca.png"
    document.write_bytes(b"image-data")
    monkeypatch.setattr(
        core,
        "extract_with_configured_vision",
        lambda _path, _data: VisionInvoice.model_validate(
            {
                "providerId": "cashoreca",
                "lines": [
                    {
                        "rawDescription": "COCA COLA LATA 330 ML 1*24",
                        "purchaseQuantity": "2",
                        "pricePerPackNet": "10.51",
                        "discountPercent": "0",
                        "lineTotalNet": "21.02",
                        "vatRate": "0.21",
                        "unitsPerPack": "24",
                    }
                ],
            }
        ),
    )

    result = extract(str(document))

    assert result.status == "EXTRACTED"
    assert result.provider_id == "cashoreca"
    assert result.lines[0].units_per_pack == Decimal("24")


def test_scanned_document_propagates_vision_failure(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    document = tmp_path / "cashoreca.png"
    document.write_bytes(b"image-data")
    monkeypatch.setattr(
        core,
        "extract_with_configured_vision",
        lambda _path, _data: (_ for _ in ()).throw(RuntimeError("HTTP 400: Gateway no admite el documento.")),
    )

    with raises(RuntimeError, match="Gateway no admite el documento"):
        extract(str(document))


def test_scanned_pdf_uses_vision_then_applies_pack_validation(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    document = tmp_path / "cashoreca.pdf"
    document.write_bytes(b"not-a-text-pdf")
    monkeypatch.setattr(
        core,
        "extract_with_configured_vision",
        lambda _path, _data: VisionInvoice.model_validate(
            {
                "providerId": "cashoreca",
                "supplierName": "CASHORECA",
                "invoiceNumber": "260112066",
                "lines": [
                    {
                        "rawDescription": "COCA COLA LATA 330 ML 1*24",
                        "purchaseQuantity": "2",
                        "pricePerPackNet": "10.51",
                        "discountPercent": "0",
                        "lineTotalNet": "21.02",
                        "vatRate": "0.21",
                        "unitsPerPack": "24",
                    }
                ],
            }
        ),
    )

    result = extract(str(document))

    assert result.status == "EXTRACTED"
    assert result.provider_id == "cashoreca"
    assert result.lines[0].validation_status == "VALID"


def test_vision_with_only_ambiguous_lines_requires_review(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    document = tmp_path / "cashoreca.pdf"
    document.write_bytes(b"not-a-text-pdf")
    monkeypatch.setattr(
        core,
        "extract_with_configured_vision",
        lambda _path, _data: VisionInvoice.model_validate(
            {
                "providerId": "cashoreca",
                "lines": [{"rawDescription": "PRODUCTO ILEGIBLE"}],
            }
        ),
    )

    result = extract(str(document))

    assert result.status == "REVIEW_REQUIRED"
    assert result.lines[0].validation_status == "REVIEW_REQUIRED"
