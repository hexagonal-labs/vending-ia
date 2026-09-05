from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from zoneinfo import ZoneInfo

from pricing_catalog_bridge.domain import (
    IngestionResult,
    ProductMatch,
    SupplierOffer,
    SupplierOfferSnapshot,
    VendingProduct,
)
from pricing_catalog_bridge.matching import ProductMatcher

from .xlsx_workbook import WorkbookSheet, write_workbook

INDEX_SCHEMA_VERSION = 1
_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class FilePricingCatalogRepository:
    """Persistencia local con un índice JSON y libros XLSX reproducibles."""

    def __init__(self, data_dir: Path, export_dir: Path | None = None) -> None:
        self._data_dir = data_dir
        self._export_dir = export_dir

    def initialize(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        (self._data_dir / "providers").mkdir(exist_ok=True)
        (self._data_dir / "catalog").mkdir(exist_ok=True)
        (self._data_dir / "templates").mkdir(exist_ok=True)
        with self._locked():
            state = self._read_index()
            self._write_index(state)
            self._write_mappings(state)
            report_path = self._data_dir / "templates" / "machine-supplier-report.xlsx"
            if not report_path.exists():
                write_workbook(report_path, _report_template())
            for provider_id, provider_state in state["providers"].items():
                self._write_catalog(provider_id, provider_state)
            self._export_existing_reports()

    def list_catalog_providers(self) -> tuple[str, ...]:
        """Devuelve proveedores que tienen al menos una oferta vigente importada."""
        self.initialize()
        with self._locked():
            state = self._read_index()
            return tuple(
                sorted(
                    _validate_provider_id(provider_id)
                    for provider_id, provider_state in state["providers"].items()
                    if provider_state.get("currentOffers")
                )
            )

    def match_products(
        self,
        provider_id: str,
        vending_products: tuple[VendingProduct, ...],
        *,
        run_id: str,
        idempotency_key: str,
    ) -> tuple[ProductMatch, ...]:
        provider_id = _validate_provider_id(provider_id)
        if not run_id.strip() or not idempotency_key.strip():
            raise ValueError("run_id e idempotency_key son obligatorios")
        self.initialize()
        with self._locked():
            state = self._read_index()
            provider_state = state["providers"].get(provider_id)
            offers = _current_offers(provider_state) if provider_state else ()
            confirmed_mappings = _confirmed_mappings(state, provider_id)
            matcher = ProductMatcher()
            matches = tuple(
                matcher.match(vending_product, offers, confirmed_mappings) for vending_product in vending_products
            )
            reviews = provider_state["pendingReviews"] if provider_state else []
            unmatched = provider_state["unmatched"] if provider_state else {}
            persisted: list[ProductMatch] = []
            for product_match in matches:
                if product_match.status == "PENDING_REVIEW":
                    review = _upsert_pending_review(reviews, provider_id, product_match, run_id, idempotency_key)
                    product_match = replace(product_match, review_id=review["reviewId"])
                if product_match.status in {"UNMATCHED", "SOURCE_INCOMPLETE"}:
                    unmatched[product_match.canonical_product_id] = _unmatched_record(product_match, run_id)
                else:
                    unmatched.pop(product_match.canonical_product_id, None)
                persisted.append(product_match)
            if provider_state is not None:
                _record_matching_run(provider_state, run_id, idempotency_key, len(vending_products))
                self._write_index(state)
                self._write_catalog(provider_id, provider_state)
                self._write_mappings(state)
            return tuple(persisted)

    def list_pending_reviews(self, provider_id: str | None = None) -> tuple[dict[str, Any], ...]:
        self.initialize()
        with self._locked():
            state = self._read_index()
            providers = [_validate_provider_id(provider_id)] if provider_id else sorted(state["providers"])
            return tuple(
                review
                for current_provider in providers
                for review in state["providers"].get(current_provider, {}).get("pendingReviews", [])
            )

    def assess_legacy_name_mappings(
        self, provider_id: str, mappings: tuple[tuple[str, str], ...]
    ) -> tuple[ProductMatch, ...]:
        """Evalúa YAML heredado sin persistir ni confirmar ninguna asociación."""
        provider_id = _validate_provider_id(provider_id)
        self.initialize()
        with self._locked():
            state = self._read_index()
            provider_state = state["providers"].get(provider_id)
            offers = _current_offers(provider_state) if provider_state else ()
            offers_by_id = {offer.supplier_product_id: offer for offer in offers}
            matcher = ProductMatcher()
            reports: list[ProductMatch] = []
            for position, (nayax_name, supplier_product_id) in enumerate(mappings, start=1):
                offer = offers_by_id.get(supplier_product_id)
                if offer is None:
                    reports.append(
                        ProductMatch(
                            canonical_product_id=f"legacy:{position}",
                            supplier_product_id=None,
                            status="SOURCE_INCOMPLETE",
                            method="sku",
                            confidence=0.0,
                            alternatives=(),
                            reason="El SKU del YAML no existe en las ofertas actuales del proveedor.",
                        )
                    )
                    continue
                reports.append(
                    matcher.match(VendingProduct(f"legacy:{position}", nayax_name), (offer,), {})
                )
            return tuple(reports)

    def record_confirmed_mapping(
        self,
        provider_id: str,
        canonical_product_id: str,
        supplier_product_id: str,
        *,
        run_id: str,
        idempotency_key: str,
    ) -> None:
        """Punto de extensión para revisión humana y migración del YAML en modo informe."""
        provider_id = _validate_provider_id(provider_id)
        if not run_id.strip() or not idempotency_key.strip():
            raise ValueError("run_id e idempotency_key son obligatorios")
        self.initialize()
        with self._locked():
            state = self._read_index()
            mappings = state["mappings"]
            mapping = {
                "providerId": provider_id,
                "canonicalProductId": canonical_product_id,
                "supplierProductId": supplier_product_id,
                "method": "confirmed_mapping",
                "confirmedAt": datetime.now(UTC).isoformat(),
                "runId": run_id,
                "idempotencyKey": idempotency_key,
            }
            state["mappings"] = [
                item
                for item in mappings
                if not (
                    item["providerId"] == provider_id and item["canonicalProductId"] == canonical_product_id
                )
            ]
            state["mappings"].append(mapping)
            self._write_index(state)
            self._write_mappings(state)

    def catalog_path_for(self, provider_id: str) -> Path:
        return self._provider_dir(_validate_provider_id(provider_id)) / "catalog.xlsx"

    def generate_machine_supplier_report(
        self, provider_id: str, machine_products: list[Any], matches: list[Any], run_id: str
    ) -> Path:
        """Crea un XLSX por combinación máquina/proveedor con PVP de Nayax.

        No reintenta ni reinterpreta el matching recibido: las filas sin match
        salen explícitamente para que se puedan corregir en la revisión humana.
        """
        provider_id = _validate_provider_id(provider_id)
        self.initialize()
        with self._locked():
            state = self._read_index()
            provider_state = state["providers"].get(provider_id, _new_provider_state())
            offers = provider_state["currentOffers"]
            matches_by_product = {match.canonical_product_id: match for match in matches}
            rows_by_machine: dict[tuple[str, str], list[tuple[object, ...]]] = {}
            unmatched_by_machine: dict[tuple[str, str], list[tuple[object, ...]]] = {}
            for product in machine_products:
                key = (product.machine_id, product.machine_name)
                match = matches_by_product.get(product.canonical_product_id)
                offer = offers.get(match.supplier_product_id) if match and match.supplier_product_id else None
                cost = _decimal(offer["unitCostWithTaxAndSurcharge"]) if offer else None
                margin = _margin(product.machine_price, cost)
                rows_by_machine.setdefault(key, []).append(
                    (
                        product.machine_name,
                        product.selection,
                        product.canonical_product_id,
                        product.product_name,
                        product.machine_price,
                        provider_id,
                        match.supplier_product_id if match else None,
                        match.status if match else "UNMATCHED",
                        cost,
                        margin,
                        match.confidence if match else Decimal("0"),
                        match.method if match else "none",
                        match.reason if match else "Sin resultado de matching.",
                    )
                )
                if cost is None:
                    unmatched_by_machine.setdefault(key, []).append(
                        (
                            product.machine_name,
                            product.selection,
                            product.canonical_product_id,
                            product.product_name,
                            product.machine_price,
                            provider_id,
                            match.status if match else "UNMATCHED",
                            match.reason if match else "Sin resultado de matching.",
                        )
                    )
            written: list[Path] = []
            for (machine_id, machine_name), rows in rows_by_machine.items():
                path = self._data_dir / "reports" / provider_id / _comparison_report_filename(
                    provider_id,
                    machine_name,
                )
                no_match = unmatched_by_machine.get((machine_id, machine_name), [])
                matched_count = len(rows) - len(no_match)
                write_workbook(
                    path,
                    (
                        WorkbookSheet(
                            "Resumen",
                            ("Indicador", "Valor"),
                            (
                                ("Máquina", machine_name),
                                ("Proveedor", provider_id),
                                ("Productos máquina", len(rows)),
                                ("Con coste comparable", matched_count),
                                ("Sin match o sin coste", len(no_match)),
                                ("Run ID", run_id),
                            ),
                        ),
                        WorkbookSheet(
                            "Comparación",
                            (
                                "Máquina", "Selección", "NayaxProductID", "ProductName", "MachinePrice",
                                "Proveedor", "SKU proveedor", "Estado match", "Coste unitario final",
                                "Margen", "Confianza", "Método", "Motivo",
                            ),
                            tuple(rows),
                        ),
                        WorkbookSheet(
                            "Sin match",
                            (
                                "Máquina", "Selección", "NayaxProductID", "ProductName", "MachinePrice",
                                "Proveedor", "Estado", "Motivo",
                            ),
                            tuple(no_match),
                        ),
                        WorkbookSheet(
                            "Parámetros",
                            ("Parámetro", "Valor"),
                            (("PVP", "MachinePrice de Nayax (fuente de verdad)"),
                             ("Coste", "Incluye IVA y recargo de equivalencia")),
                        ),
                    ),
                )
                self._export_comparison(provider_id, path)
                written.append(path)
            if not written:
                raise ValueError("No hay productos de máquina para generar el informe")
            return written[0] if len(written) == 1 else self._write_report_manifest(provider_id, run_id, written)

    def _write_report_manifest(self, provider_id: str, run_id: str, reports: list[Path]) -> Path:
        manifest = self._data_dir / "reports" / provider_id / f"run-{run_id}.json"
        _atomic_write_text(manifest, json.dumps({"reports": [str(path) for path in reports]}, indent=2) + "\n")
        return manifest

    def record_supplier_snapshot(
        self, snapshot: SupplierOfferSnapshot, idempotency_key: str
    ) -> IngestionResult:
        provider_id = _validate_provider_id(snapshot.provider_id)
        if not idempotency_key.strip():
            raise ValueError("idempotency_key es obligatorio")
        self.initialize()
        source_hash = _snapshot_hash(snapshot)

        with self._locked():
            state = self._read_index()
            existing = _find_import(state, idempotency_key, source_hash)
            if existing is not None:
                return IngestionResult(
                    provider_id=existing["providerId"],
                    import_id=existing["importId"],
                    source_hash=existing["sourceHash"],
                    ingested_at=datetime.fromisoformat(existing["ingestedAt"]),
                    inserted_offers=0,
                    duplicate=True,
                    catalog_path=str(self.catalog_path_for(existing["providerId"])),
                )

            ingested_at = datetime.now(UTC)
            import_id = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16]
            provider_state = state["providers"].setdefault(provider_id, _new_provider_state())
            record = {
                "providerId": provider_id,
                "importId": import_id,
                "idempotencyKey": idempotency_key,
                "sourceHash": source_hash,
                "observedAt": snapshot.observed_at.isoformat(),
                "ingestedAt": ingested_at.isoformat(),
                "offerCount": len(snapshot.offers),
                "sourceType": "supplier_api_snapshot",
            }
            provider_state["imports"].append(record)
            state["imports"].append(record)
            for offer in snapshot.offers:
                offer_record = {
                    "supplierProductId": offer.supplier_product_id,
                    "name": offer.name,
                    "unitCostWithTaxAndSurcharge": str(offer.unit_cost_with_tax_and_surcharge),
                    "available": offer.available,
                    "barcode": offer.barcode,
                    "supplierReference": offer.supplier_reference,
                    "observedAt": snapshot.observed_at.isoformat(),
                    "ingestedAt": ingested_at.isoformat(),
                    "importId": import_id,
                    "sourceHash": source_hash,
                }
                provider_state["priceHistory"].append(offer_record)
                provider_state["currentOffers"][offer.supplier_product_id] = offer_record

            self._write_source_snapshot(provider_id, source_hash, snapshot)
            self._write_index(state)
            self._write_catalog(provider_id, provider_state)
            return IngestionResult(
                provider_id=provider_id,
                import_id=import_id,
                source_hash=source_hash,
                ingested_at=ingested_at,
                inserted_offers=len(snapshot.offers),
                duplicate=False,
                catalog_path=str(self.catalog_path_for(provider_id)),
            )

    def record_invoice(self, invoice: Any, idempotency_key: str, equivalence_surcharge_rate: Any) -> IngestionResult:
        """Incorpora sólo las líneas verificadas de una factura al catálogo actual.

        El orden de ``ingestedAt`` representa el orden real de adjuntar el
        documento: por eso una factura posterior reemplaza el coste vigente,
        aunque su fecha de emisión sea más antigua o su precio haya bajado.
        """
        provider_id = _validate_provider_id(str(invoice.provider_id))
        if not idempotency_key.strip():
            raise ValueError("idempotency_key es obligatorio")
        self.initialize()
        with self._locked():
            state = self._read_index()
            existing = _find_invoice_import(state, provider_id, invoice, idempotency_key)
            if existing is not None:
                return IngestionResult(
                    provider_id=existing["providerId"],
                    import_id=existing["importId"],
                    source_hash=existing["sourceHash"],
                    ingested_at=datetime.fromisoformat(existing["ingestedAt"]),
                    inserted_offers=0,
                    duplicate=True,
                    catalog_path=str(self.catalog_path_for(existing["providerId"])),
                )

            ingested_at = datetime.now(UTC)
            import_id = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16]
            provider_state = state["providers"].setdefault(provider_id, _new_provider_state())
            valid_lines = [line for line in invoice.lines if line.validation_status == "VALID"]
            record = {
                "providerId": provider_id,
                "importId": import_id,
                "idempotencyKey": idempotency_key,
                "sourceHash": invoice.source_hash,
                "observedAt": invoice.ingested_at.isoformat(),
                "ingestedAt": ingested_at.isoformat(),
                "offerCount": len(valid_lines),
                "sourceType": "invoice",
                "invoiceNumber": invoice.invoice_number,
                "invoiceStatus": invoice.status,
            }
            provider_state["imports"].append(record)
            state["imports"].append(record)
            surcharge = _decimal(str(equivalence_surcharge_rate))
            for line in valid_lines:
                units = _decimal(str(line.units_per_pack)) if line.units_per_pack is not None else None
                if units is None or units <= 0:
                    continue
                offer = {
                    "supplierProductId": _invoice_supplier_product_id(line),
                    "name": str(line.raw_description),
                    "unitCostWithTaxAndSurcharge": str(
                        _decimal(str(line.pack_price_net)) * (1 + _decimal(str(line.vat_rate)) + surcharge) / units
                    ),
                    "available": True,
                    "barcode": _as_optional_text(line.barcode),
                    "supplierReference": _as_optional_text(line.supplier_reference),
                    "observedAt": invoice.ingested_at.isoformat(),
                    "ingestedAt": ingested_at.isoformat(),
                    "importId": import_id,
                    "sourceHash": invoice.source_hash,
                    "sourceType": "invoice",
                    "invoiceNumber": invoice.invoice_number,
                    "packExpression": line.pack_expression,
                    "unitsPerPack": str(units),
                    "vatRate": str(line.vat_rate),
                    "equivalenceSurchargeRate": str(surcharge),
                }
                provider_state["priceHistory"].append(offer)
                provider_state["currentOffers"][offer["supplierProductId"]] = offer

            self._write_invoice_source(provider_id, invoice.source_hash, invoice)
            self._write_index(state)
            self._write_catalog(provider_id, provider_state)
            return IngestionResult(
                provider_id=provider_id,
                import_id=import_id,
                source_hash=invoice.source_hash,
                ingested_at=ingested_at,
                inserted_offers=len(valid_lines),
                duplicate=False,
                catalog_path=str(self.catalog_path_for(provider_id)),
            )

    def _provider_dir(self, provider_id: str) -> Path:
        return self._data_dir / "providers" / provider_id

    def _index_path(self) -> Path:
        return self._data_dir / "index.json"

    def _read_index(self) -> dict[str, Any]:
        path = self._index_path()
        if not path.exists():
            return {"schemaVersion": INDEX_SCHEMA_VERSION, "imports": [], "providers": {}, "mappings": []}
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or loaded.get("schemaVersion") != INDEX_SCHEMA_VERSION:
            raise ValueError("index.json no tiene el esquema soportado")
        if not isinstance(loaded.get("imports"), list) or not isinstance(loaded.get("providers"), dict):
            raise ValueError("index.json está incompleto")
        if not isinstance(loaded.get("mappings", []), list):
            raise ValueError("index.json tiene mappings inválidos")
        loaded.setdefault("mappings", [])
        for provider_state in loaded["providers"].values():
            if not isinstance(provider_state, dict):
                raise ValueError("index.json tiene un proveedor inválido")
            provider_state.setdefault("pendingReviews", [])
            provider_state.setdefault("unmatched", {})
            provider_state.setdefault("currentOffers", {})
            provider_state.setdefault("priceHistory", [])
            provider_state.setdefault("imports", [])
            provider_state.setdefault("matchingRuns", [])
        return loaded

    def _write_index(self, state: dict[str, Any]) -> None:
        _atomic_write_text(self._index_path(), json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    def _write_source_snapshot(self, provider_id: str, source_hash: str, snapshot: SupplierOfferSnapshot) -> None:
        source_dir = self._provider_dir(provider_id) / "snapshots"
        source_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "contractVersion": "supplier-offer-snapshot/v1",
            "providerId": provider_id,
            "retrievedAt": snapshot.observed_at.isoformat(),
            "products": [
                {
                    "supplierProductId": offer.supplier_product_id,
                    "name": offer.name,
                    "unitCostWithTaxAndSurcharge": str(offer.unit_cost_with_tax_and_surcharge),
                    "available": offer.available,
                    "barcode": offer.barcode,
                    "supplierReference": offer.supplier_reference,
                }
                for offer in snapshot.offers
            ],
        }
        _atomic_write_text(source_dir / f"{source_hash}.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def _write_invoice_source(self, provider_id: str, source_hash: str, invoice: Any) -> None:
        source_dir = self._provider_dir(provider_id) / "invoices"
        source_dir.mkdir(parents=True, exist_ok=True)
        payload = invoice.model_dump(mode="json", by_alias=True)
        _atomic_write_text(source_dir / f"{source_hash}.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def _write_catalog(self, provider_id: str, provider_state: dict[str, Any]) -> None:
        current_offers = sorted(provider_state["currentOffers"].values(), key=lambda offer: offer["supplierProductId"])
        history = provider_state["priceHistory"]
        imports = provider_state["imports"]
        pending_reviews = provider_state.get("pendingReviews", [])
        unmatched = provider_state.get("unmatched", {}).values()
        catalog_path = self.catalog_path_for(provider_id)
        write_workbook(
            catalog_path,
            (
                WorkbookSheet(
                    "Ofertas actuales",
                    (
                        "SKU proveedor",
                        "Referencia proveedor",
                        "Código de barras",
                        "Nombre",
                        "Coste unitario final",
                        "Disponible",
                        "Observado",
                        "Importado",
                        "Hash fuente (16)",
                    ),
                    tuple(
                        (
                            offer["supplierProductId"],
                            offer.get("supplierReference"),
                            offer.get("barcode"),
                            offer["name"],
                            _decimal(offer["unitCostWithTaxAndSurcharge"]),
                            offer["available"],
                            _datetime(offer["observedAt"]),
                            _datetime(offer["ingestedAt"]),
                            _short_hash(offer["sourceHash"]),
                        )
                        for offer in current_offers
                    ),
                ),
                WorkbookSheet(
                    "Historial precios",
                    (
                        "SKU proveedor",
                        "Referencia proveedor",
                        "Código de barras",
                        "Nombre",
                        "Coste unitario final",
                        "Disponible",
                        "Observado",
                        "Importado",
                        "Importación",
                        "Hash fuente (16)",
                    ),
                    tuple(
                        (
                            offer["supplierProductId"],
                            offer.get("supplierReference"),
                            offer.get("barcode"),
                            offer["name"],
                            _decimal(offer["unitCostWithTaxAndSurcharge"]),
                            offer["available"],
                            _datetime(offer["observedAt"]),
                            _datetime(offer["ingestedAt"]),
                            offer["importId"],
                            _short_hash(offer["sourceHash"]),
                        )
                        for offer in history
                    ),
                ),
                WorkbookSheet(
                    "Importaciones",
                    (
                        "Importación",
                        "Tipo",
                        "Ofertas",
                        "Observado",
                        "Importado",
                        "Hash fuente (16)",
                        "Idempotency key",
                    ),
                    tuple(
                        (
                            item["importId"],
                            item["sourceType"],
                            item["offerCount"],
                            _datetime(item["observedAt"]),
                            _datetime(item["ingestedAt"]),
                            _short_hash(item["sourceHash"]),
                            item["idempotencyKey"],
                        )
                        for item in imports
                    ),
                ),
                WorkbookSheet(
                    "Sin match",
                    ("Producto Nayax", "Estado", "Motivo", "Confianza", "Candidatos", "Run ID"),
                    tuple(
                        (
                            item["canonicalProductId"],
                            item["status"],
                            item["reason"],
                            item["confidence"],
                            item["alternatives"],
                            item["runId"],
                        )
                        for item in unmatched
                    ),
                ),
                WorkbookSheet(
                    "Pendientes revisión",
                    ("Revisión", "Producto Nayax", "Candidato", "Confianza", "Motivo", "Creado", "Run ID"),
                    tuple(
                        (
                            item["reviewId"],
                            item["canonicalProductId"],
                            item["supplierProductId"],
                            item["confidence"],
                            item["reason"],
                            _datetime(item["createdAt"]),
                            item["runId"],
                        )
                        for item in pending_reviews
                    ),
                ),
                WorkbookSheet(
                    "Parámetros",
                    ("Parámetro", "Valor", "Nota"),
                    (("providerId", provider_id, "Identificador estable del proveedor"),),
                ),
            ),
        )
        self._export_catalog(provider_id, catalog_path)

    def _export_catalog(self, provider_id: str, catalog_path: Path) -> None:
        if self._export_dir is None:
            return
        _copy_atomically(catalog_path, self._export_dir / "catalogos" / provider_id / "catalog.xlsx")

    def _export_comparison(self, provider_id: str, report_path: Path) -> None:
        if self._export_dir is None:
            return
        _copy_atomically(report_path, self._export_dir / "comparaciones" / provider_id / report_path.name)

    def _export_existing_reports(self) -> None:
        if self._export_dir is None:
            return
        reports_directory = self._data_dir / "reports"
        if not reports_directory.is_dir():
            return
        for provider_directory in reports_directory.iterdir():
            if not provider_directory.is_dir():
                continue
            provider_id = _validate_provider_id(provider_directory.name)
            for report_path in provider_directory.glob("*.xlsx"):
                self._export_comparison(provider_id, report_path)

    def _write_mappings(self, state: dict[str, Any]) -> None:
        write_workbook(
            self._data_dir / "catalog" / "product-mappings.xlsx",
            (
                WorkbookSheet(
                    "Mappings",
                    ("NayaxProductID", "Proveedor", "SKU proveedor", "Método", "Confirmado en", "Run ID"),
                    tuple(
                        (
                            item["canonicalProductId"],
                            item["providerId"],
                            item["supplierProductId"],
                            item["method"],
                            _datetime(item["confirmedAt"]),
                            item["runId"],
                        )
                        for item in state["mappings"]
                    ),
                ),
                WorkbookSheet("Aliases", ("Proveedor", "Alias", "NayaxProductID", "Creado en")),
                WorkbookSheet(
                    "Pendientes revisión",
                    ("Revisión", "Proveedor", "Producto", "Motivo", "Creado", "Run ID"),
                    tuple(
                        (
                            item["reviewId"],
                            provider_id,
                            item["canonicalProductId"],
                            item["reason"],
                            _datetime(item["createdAt"]),
                            item["runId"],
                        )
                        for provider_id, provider_state in state["providers"].items()
                        for item in provider_state.get("pendingReviews", [])
                    ),
                ),
            ),
        )

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self._data_dir / ".pricing-catalog.lock"
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _mappings_template() -> tuple[WorkbookSheet, ...]:
    return (
        WorkbookSheet(
            "Mappings",
            ("NayaxProductID", "Proveedor", "SKU proveedor", "Método", "Confirmado", "Confirmado en"),
        ),
        WorkbookSheet("Aliases", ("Proveedor", "Alias", "NayaxProductID", "Creado en")),
        WorkbookSheet("Pendientes revisión", ("Revisión", "Proveedor", "Producto", "Motivo", "Creado")),
    )


def _copy_atomically(source: Path, destination: Path) -> None:
    """Publica un Excel terminado sin que un lector vea una copia parcial."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        shutil.copy2(source, temporary_path)
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def _report_template() -> tuple[WorkbookSheet, ...]:
    return (
        WorkbookSheet("Resumen", ("Indicador", "Valor")),
        WorkbookSheet(
            "Comparación",
            (
                "Máquina",
                "Selección",
                "NayaxProductID",
                "ProductName",
                "MachinePrice",
                "Proveedor",
                "SKU proveedor",
                "Estado match",
                "Coste unitario final",
                "Margen",
            ),
        ),
        WorkbookSheet("Sin match", ("Máquina", "ProductName", "Proveedor", "Motivo", "Candidatos")),
        WorkbookSheet("Parámetros", ("Parámetro", "Valor")),
        WorkbookSheet("Origen", ("Run ID", "Fuente", "Fecha", "Hash")),
    )


def _validate_provider_id(provider_id: str) -> str:
    normalized = provider_id.strip().lower()
    if not _PROVIDER_ID.fullmatch(normalized):
        raise ValueError("provider_id debe usar letras minúsculas, números y guiones")
    return normalized


def _snapshot_hash(snapshot: SupplierOfferSnapshot) -> str:
    payload = {
        "providerId": _validate_provider_id(snapshot.provider_id),
        "retrievedAt": snapshot.observed_at.isoformat(),
        "products": [
            {
                "supplierProductId": offer.supplier_product_id,
                "name": offer.name,
                "unitCostWithTaxAndSurcharge": str(offer.unit_cost_with_tax_and_surcharge),
                "available": offer.available,
                "barcode": offer.barcode,
                "supplierReference": offer.supplier_reference,
            }
            for offer in snapshot.offers
        ],
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _find_import(state: dict[str, Any], idempotency_key: str, source_hash: str) -> dict[str, Any] | None:
    for item in state["imports"]:
        if not isinstance(item, dict):
            raise ValueError("index.json contiene una importación inválida")
        if item["idempotencyKey"] == idempotency_key or item["sourceHash"] == source_hash:
            return item
    return None


def _find_invoice_import(
    state: dict[str, Any], provider_id: str, invoice: Any, idempotency_key: str
) -> dict[str, Any] | None:
    for item in state["imports"]:
        if not isinstance(item, dict):
            raise ValueError("index.json contiene una importación inválida")
        if item.get("idempotencyKey") == idempotency_key or item.get("sourceHash") == invoice.source_hash:
            return item
        if (
            invoice.invoice_number
            and item.get("providerId") == provider_id
            and item.get("sourceType") == "invoice"
            and item.get("invoiceNumber") == invoice.invoice_number
        ):
            return item
    return None


def _invoice_supplier_product_id(line: Any) -> str:
    """Usa referencias como evidencia estable, nunca como identidad canónica.

    Si el proveedor no da referencia ni EAN, el hash del nombre normalizado
    permite conservar su historial hasta que una revisión humana lo aclare.
    """
    if _as_optional_text(line.supplier_reference):
        return f"invoice-ref:{line.supplier_reference}"
    if _as_optional_text(line.barcode):
        return f"invoice-ean:{line.barcode}"
    normalized = re.sub(r"\s+", " ", str(line.raw_description).strip().lower())
    return f"invoice-name:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]}"


def _new_provider_state() -> dict[str, Any]:
    return {
        "currentOffers": {},
        "priceHistory": [],
        "imports": [],
        "pendingReviews": [],
        "unmatched": {},
        "matchingRuns": [],
    }


def _current_offers(provider_state: dict[str, Any]) -> tuple[SupplierOffer, ...]:
    offers: list[SupplierOffer] = []
    for item in provider_state["currentOffers"].values():
        if not isinstance(item, dict):
            raise ValueError("index.json contiene una oferta actual inválida")
        offers.append(
            SupplierOffer(
                supplier_product_id=str(item["supplierProductId"]),
                name=str(item["name"]),
                unit_cost_with_tax_and_surcharge=_decimal(str(item["unitCostWithTaxAndSurcharge"])),
                available=bool(item["available"]),
                barcode=_as_optional_text(item.get("barcode")),
                supplier_reference=_as_optional_text(item.get("supplierReference")),
            )
        )
    return tuple(offers)


def _confirmed_mappings(state: dict[str, Any], provider_id: str) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for item in state["mappings"]:
        if not isinstance(item, dict):
            raise ValueError("index.json contiene un mapping inválido")
        if item.get("providerId") == provider_id and item.get("method") == "confirmed_mapping":
            mappings[str(item["canonicalProductId"])] = str(item["supplierProductId"])
    return mappings


def _upsert_pending_review(
    reviews: list[dict[str, Any]],
    provider_id: str,
    product_match: ProductMatch,
    run_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    review_id = hashlib.sha256(f"{provider_id}:{product_match.canonical_product_id}".encode()).hexdigest()[:16]
    review = {
        "reviewId": review_id,
        "canonicalProductId": product_match.canonical_product_id,
        "supplierProductId": product_match.supplier_product_id,
        "confidence": product_match.confidence,
        "reason": product_match.reason,
        "runId": run_id,
        "idempotencyKey": idempotency_key,
        "alternatives": [
            {
                "supplierProductId": candidate.supplier_product_id,
                "name": candidate.name,
                "confidence": candidate.confidence,
                "reason": candidate.reason,
            }
            for candidate in product_match.alternatives
        ],
        "createdAt": datetime.now(UTC).isoformat(),
    }
    for position, previous in enumerate(reviews):
        if previous.get("reviewId") == review_id:
            review["createdAt"] = previous["createdAt"]
            reviews[position] = review
            return review
    reviews.append(review)
    return review


def _unmatched_record(product_match: ProductMatch, run_id: str) -> dict[str, Any]:
    return {
        "canonicalProductId": product_match.canonical_product_id,
        "status": product_match.status,
        "confidence": product_match.confidence,
        "reason": product_match.reason,
        "runId": run_id,
        "alternatives": "; ".join(
            f"{candidate.supplier_product_id}: {candidate.name} ({candidate.confidence:.0%})"
            for candidate in product_match.alternatives
        ),
    }


def _as_optional_text(value: object) -> str | None:
    return str(value) if isinstance(value, str) and value else None


def _record_matching_run(
    provider_state: dict[str, Any], run_id: str, idempotency_key: str, product_count: int
) -> None:
    runs = provider_state["matchingRuns"]
    if any(item.get("idempotencyKey") == idempotency_key for item in runs):
        return
    runs.append(
        {
            "runId": run_id,
            "idempotencyKey": idempotency_key,
            "productCount": product_count,
            "matchedAt": datetime.now(UTC).isoformat(),
        }
    )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        mode="w",
        encoding="utf-8",
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    try:
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _decimal(value: str) -> Any:
    from decimal import Decimal

    return Decimal(value)


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _short_hash(value: str) -> str:
    return value[:16]


def _margin(machine_price: Decimal | None, cost: Decimal | None) -> Decimal | None:
    if machine_price is None or machine_price <= 0 or cost is None:
        return None
    return (machine_price - cost) / machine_price


def _safe_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", normalized).strip("-") or "machine"


def _comparison_report_filename(provider_id: str, machine_name: str, generated_at: datetime | None = None) -> str:
    """Nombre legible y local de los Excel de comparación."""
    local_time = (generated_at or datetime.now(ZoneInfo("Europe/Madrid"))).astimezone(ZoneInfo("Europe/Madrid"))
    timestamp = local_time.strftime("%d_%m_%Y_%H:%M")
    return f"{_safe_name(provider_id)}-{_safe_name(machine_name)}-{timestamp}.xlsx"
