from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from pricing_catalog_bridge.application.contracts import SupplierInvoiceIngestionV1
from pricing_catalog_bridge.domain import ProductMatch, SupplierOffer, SupplierOfferSnapshot, VendingProduct
from pricing_catalog_bridge.infrastructure import FilePricingCatalogRepository
from pricing_catalog_bridge.infrastructure.catalog_repository import _comparison_report_filename


def _snapshot(cost: str = "0.62") -> SupplierOfferSnapshot:
    return SupplierOfferSnapshot(
        provider_id="distribuidora-mayorista",
        observed_at=datetime(2026, 9, 4, 10, 0, tzinfo=UTC),
        offers=(
            SupplierOffer("offer-1101", "Refresco cola lata 330 ml", Decimal(cost), True),
            SupplierOffer("offer-1102", "Agua mineral 50 cl", Decimal("0.24"), False),
        ),
    )


def test_initialization_creates_the_owned_excel_templates(tmp_path: Path) -> None:
    repository = FilePricingCatalogRepository(tmp_path / "pricing-data")

    repository.initialize()

    assert (tmp_path / "pricing-data" / "index.json").is_file()
    assert (tmp_path / "pricing-data" / "catalog" / "product-mappings.xlsx").is_file()
    assert (tmp_path / "pricing-data" / "templates" / "machine-supplier-report.xlsx").is_file()


def test_snapshot_updates_current_catalog_and_keeps_append_only_history(tmp_path: Path) -> None:
    data_dir = tmp_path / "pricing-data"
    repository = FilePricingCatalogRepository(data_dir)

    first = repository.record_supplier_snapshot(_snapshot(), "run-001")
    duplicate_by_key = repository.record_supplier_snapshot(_snapshot("0.80"), "run-001")
    duplicate_by_hash = repository.record_supplier_snapshot(_snapshot(), "run-002")
    second = repository.record_supplier_snapshot(_snapshot("0.80"), "run-003")

    assert first.duplicate is False
    assert first.inserted_offers == 2
    assert duplicate_by_key.duplicate is True
    assert duplicate_by_key.inserted_offers == 0
    assert duplicate_by_hash.duplicate is True
    assert second.duplicate is False
    assert second.inserted_offers == 2

    index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
    provider = index["providers"]["distribuidora-mayorista"]
    assert len(provider["imports"]) == 2
    assert len(provider["priceHistory"]) == 4
    assert provider["currentOffers"]["offer-1101"]["unitCostWithTaxAndSurcharge"] == "0.80"
    assert (data_dir / "providers" / "distribuidora-mayorista" / "catalog.xlsx").is_file()
    assert len(list((data_dir / "providers" / "distribuidora-mayorista" / "snapshots").glob("*.json"))) == 2


def test_list_catalog_providers_only_returns_providers_with_current_offers(tmp_path: Path) -> None:
    repository = FilePricingCatalogRepository(tmp_path / "pricing-data")
    repository.initialize()

    assert repository.list_catalog_providers() == ()

    repository.record_supplier_snapshot(_snapshot(), "run-001")

    assert repository.list_catalog_providers() == ("distribuidora-mayorista",)


def test_catalog_workbook_is_valid_xlsx_with_auditable_sheets(tmp_path: Path) -> None:
    repository = FilePricingCatalogRepository(tmp_path / "pricing-data")
    result = repository.record_supplier_snapshot(_snapshot(), "run-001")

    with ZipFile(result.catalog_path) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")

    assert "Ofertas actuales" in workbook
    assert "Historial precios" in workbook
    assert "Refresco cola lata 330 ml" in sheet
    assert "0.62" in sheet
    assert sheet.index("<sheetViews>") < sheet.index("<cols>") < sheet.index("<sheetData>")


def test_catalogs_and_comparisons_are_exported_to_the_project_directory(tmp_path: Path) -> None:
    data_dir = tmp_path / "pricing-data"
    export_dir = tmp_path / "project-reports"
    repository = FilePricingCatalogRepository(data_dir, export_dir)
    repository.record_supplier_snapshot(_snapshot(), "run-001")

    exported_catalog = export_dir / "catalogos" / "distribuidora-mayorista" / "catalog.xlsx"
    assert exported_catalog.is_file()

    report = repository.generate_machine_supplier_report(
        "distribuidora-mayorista",
        [
            SimpleNamespace(
                machine_id="42",
                machine_name="Máquina prueba",
                selection="1",
                canonical_product_id="nayax:1",
                product_name="Refresco prueba",
                machine_price=Decimal("1.50"),
            )
        ],
        [ProductMatch("nayax:1", None, "UNMATCHED", "none", 0.0, (), "No encontrado.")],
        run_id="pricing-001",
    )

    exported_report = export_dir / "comparaciones" / "distribuidora-mayorista" / report.name
    assert report.is_file()
    assert exported_report.is_file()
    assert exported_report.read_bytes() == report.read_bytes()


def test_comparison_report_filename_uses_provider_machine_and_local_timestamp() -> None:
    filename = _comparison_report_filename(
        "cashoreca",
        "Máquina prueba",
        datetime(2026, 9, 6, 21, 22, tzinfo=UTC),
    )

    assert filename == "cashoreca-Maquina-prueba-06_09_2026_23:22.xlsx"


def test_matching_persists_only_ambiguous_and_unmatched_products(tmp_path: Path) -> None:
    repository = FilePricingCatalogRepository(tmp_path / "pricing-data")
    repository.record_supplier_snapshot(
        SupplierOfferSnapshot(
            provider_id="distribuidora-mayorista",
            observed_at=datetime(2026, 9, 4, 10, 0, tzinfo=UTC),
            offers=(
                SupplierOffer("cola", "Coca Cola Lata 330 ML", Decimal("0.62"), True),
                SupplierOffer("cola-zero", "Coca Cola Zero Azucar Lata 330 ML", Decimal("0.62"), True),
                SupplierOffer("pringles-70", "Pringles Original 70 g", Decimal("0.90"), True),
            ),
        ),
        "snapshot-001",
    )

    results = repository.match_products(
        "distribuidora-mayorista",
        (
            VendingProduct("nayax:1", "Coca Cola Lata 0,33 L"),
            VendingProduct("nayax:2", "Coca Cola Zero Lata 330 ML"),
            VendingProduct("nayax:3", "Pringles Original 40 g"),
        ),
        run_id="matching-001",
        idempotency_key="matching-001",
    )
    repeated_results = repository.match_products(
        "distribuidora-mayorista",
        (
            VendingProduct("nayax:1", "Coca Cola Lata 0,33 L"),
            VendingProduct("nayax:2", "Coca Cola Zero Lata 330 ML"),
            VendingProduct("nayax:3", "Pringles Original 40 g"),
        ),
        run_id="matching-001",
        idempotency_key="matching-001",
    )

    assert [result.status for result in results] == ["MATCHED_EXACT", "PENDING_REVIEW", "UNMATCHED"]
    assert results[1].review_id is not None
    reviews = repository.list_pending_reviews("distribuidora-mayorista")
    assert len(reviews) == 1
    assert reviews[0]["canonicalProductId"] == "nayax:2"

    index = json.loads((tmp_path / "pricing-data" / "index.json").read_text(encoding="utf-8"))
    provider = index["providers"]["distribuidora-mayorista"]
    assert set(provider["unmatched"]) == {"nayax:3"}
    assert len(provider["matchingRuns"]) == 1
    assert repeated_results[1].review_id == results[1].review_id


def test_confirmed_mapping_is_used_without_changing_history(tmp_path: Path) -> None:
    repository = FilePricingCatalogRepository(tmp_path / "pricing-data")
    repository.record_supplier_snapshot(_snapshot(), "run-001")
    repository.record_confirmed_mapping(
        "distribuidora-mayorista",
        "nayax:1101",
        "offer-1101",
        run_id="mapping-001",
        idempotency_key="mapping-001",
    )

    result = repository.match_products(
        "distribuidora-mayorista",
        (VendingProduct("nayax:1101", "Nombre totalmente distinto"),),
        run_id="matching-confirmed-001",
        idempotency_key="matching-confirmed-001",
    )[0]

    assert result.status == "MATCHED_CONFIRMED"
    assert result.supplier_product_id == "offer-1101"


def test_legacy_yaml_mappings_are_assessed_without_being_persisted(tmp_path: Path) -> None:
    data_dir = tmp_path / "pricing-data"
    repository = FilePricingCatalogRepository(data_dir)
    repository.record_supplier_snapshot(_snapshot(), "run-001")

    results = repository.assess_legacy_name_mappings(
        "distribuidora-mayorista",
        (("Refresco cola lata 330 ml", "offer-1101"), ("Refresco cola lata 500 ml", "offer-1101")),
    )

    assert [result.status for result in results] == ["MATCHED_EXACT", "UNMATCHED"]
    index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
    assert index["mappings"] == []


def test_invoice_uses_last_attached_valid_price_and_keeps_history(tmp_path: Path) -> None:
    repository = FilePricingCatalogRepository(tmp_path / "pricing-data")
    first = SupplierInvoiceIngestionV1.model_validate(
        {
            "contractVersion": "supplier-invoice-ingestion/v1",
            "providerId": "cashoreca",
            "invoiceNumber": "A-1",
            "sourceHash": "a" * 64,
            "ingestedAt": "2026-09-01T10:00:00+00:00",
            "status": "EXTRACTED",
            "lines": [
                {
                    "rawDescription": "COCA COLA LATA 330 ML 1*24",
                    "supplierReference": "cola-330",
                    "purchaseQuantity": "2",
                    "priceScope": "pack",
                    "packExpression": "1*24",
                    "unitsPerPack": "24",
                    "packPriceNet": "10.00",
                    "lineTotalNet": "20.00",
                    "vatRate": "0.21",
                    "validationStatus": "VALID",
                }
            ],
        }
    )
    second = first.model_copy(update={"invoice_number": "A-2", "source_hash": "b" * 64})

    repository.record_invoice(first, "invoice-001", Decimal("0.052"))
    repository.record_invoice(second.model_copy(update={"lines": [
        first.lines[0].model_copy(update={"pack_price_net": Decimal("12.00"), "line_total_net": Decimal("24.00")})
    ]}), "invoice-002", Decimal("0.052"))

    state = json.loads((tmp_path / "pricing-data" / "index.json").read_text(encoding="utf-8"))
    provider = state["providers"]["cashoreca"]
    assert len(provider["priceHistory"]) == 2
    assert Decimal(provider["currentOffers"]["invoice-ref:cola-330"]["unitCostWithTaxAndSurcharge"]) == Decimal("0.631")
