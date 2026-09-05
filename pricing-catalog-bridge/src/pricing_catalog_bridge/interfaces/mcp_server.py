from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from pricing_catalog_bridge.application.contracts import (
    GenerateMachineSupplierReportRequestV1,
    LegacyMappingReportRequestV1,
    MatchProductsRequestV1,
    RecordInvoiceRequestV1,
    RecordSnapshotRequestV1,
)
from pricing_catalog_bridge.infrastructure import FilePricingCatalogRepository


def create_server(data_dir: Path | None = None) -> FastMCP:
    export_dir = os.getenv("PRICING_EXPORT_DIR", "").strip()
    repository = FilePricingCatalogRepository(
        data_dir or Path(os.getenv("PRICING_DATA_DIR", "pricing-data")),
        Path(export_dir) if export_dir else None,
    )
    server = FastMCP(
        "pricing-catalog-bridge",
        instructions=(
            "Gestiona el catálogo local de precios de proveedores. "
            "No consulta Nayax ni proveedores externos y no calcula márgenes."
        ),
    )

    @server.tool()
    def initialize_catalog() -> dict[str, str]:
        """Crea el índice y las plantillas Excel si todavía no existen."""
        repository.initialize()
        return {
            "dataDir": str(repository._data_dir),
            "mappingsWorkbook": str(repository._data_dir / "catalog" / "product-mappings.xlsx"),
        }

    @server.tool()
    def list_catalog_providers() -> dict[str, Any]:
        """Lista los proveedores con productos vigentes en su catálogo local."""
        provider_ids = repository.list_catalog_providers()
        return {"count": len(provider_ids), "providerIds": list(provider_ids)}

    @server.tool()
    def record_supplier_snapshot(snapshot: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        """Registra una oferta API v1 sin sobrescribir el historial.

        `snapshot` debe seguir supplier-offer-snapshot/v1. Repetir el mismo
        `idempotency_key` o el mismo contenido no añade filas nuevas.
        """
        request = RecordSnapshotRequestV1.model_validate(
            {"snapshot": snapshot, "idempotencyKey": idempotency_key}
        )
        result = repository.record_supplier_snapshot(request.snapshot.to_domain(), request.idempotency_key)
        return {
            "providerId": result.provider_id,
            "importId": result.import_id,
            "sourceHash": result.source_hash,
            "ingestedAt": result.ingested_at.isoformat(),
            "insertedOffers": result.inserted_offers,
            "duplicate": result.duplicate,
            "catalogPath": result.catalog_path,
        }

    @server.tool()
    def record_supplier_invoice(
        invoice: dict[str, Any], idempotency_key: str, equivalence_surcharge_rate: str = "0"
    ) -> dict[str, Any]:
        """Registra una factura extraída, sin aceptar líneas que pidan revisión.

        El último documento adjuntado para un producto fija su coste actual. El
        coste resultante incluye IVA y el recargo de equivalencia indicado.
        """
        request = RecordInvoiceRequestV1.model_validate(
            {
                "invoice": invoice,
                "idempotencyKey": idempotency_key,
                "equivalenceSurchargeRate": equivalence_surcharge_rate,
            }
        )
        result = repository.record_invoice(
            request.invoice,
            request.idempotency_key,
            request.equivalence_surcharge_rate,
        )
        return {
            "providerId": result.provider_id,
            "importId": result.import_id,
            "sourceHash": result.source_hash,
            "ingestedAt": result.ingested_at.isoformat(),
            "insertedOffers": result.inserted_offers,
            "duplicate": result.duplicate,
            "catalogPath": result.catalog_path,
        }

    @server.tool()
    def match_products(
        provider_id: str,
        vending_products: list[dict[str, Any]],
        run_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Compara productos Nayax con las ofertas vigentes de un proveedor.

        Los resultados ambiguos se guardan en Pendientes revisión. Los tamaños,
        formatos y EAN contradictorios no se confirman automáticamente.
        """
        request = MatchProductsRequestV1.model_validate(
            {
                "providerId": provider_id,
                "vendingProducts": vending_products,
                "runId": run_id,
                "idempotencyKey": idempotency_key,
            }
        )
        results = repository.match_products(
            request.provider_id,
            tuple(product.to_domain() for product in request.vending_products),
            run_id=request.run_id,
            idempotency_key=request.idempotency_key,
        )
        return {
            "providerId": request.provider_id,
            "matches": [
                {
                    "canonicalProductId": result.canonical_product_id,
                    "supplierProductId": result.supplier_product_id,
                    "status": result.status,
                    "method": result.method,
                    "confidence": result.confidence,
                    "alternatives": [
                        {
                            "supplierProductId": alternative.supplier_product_id,
                            "name": alternative.name,
                            "confidence": alternative.confidence,
                            "reason": alternative.reason,
                        }
                        for alternative in result.alternatives
                    ],
                    "reason": result.reason,
                    "reviewId": result.review_id,
                }
                for result in results
            ],
        }

    @server.tool()
    def list_pending_reviews(provider_id: str | None = None) -> dict[str, Any]:
        """Lista asociaciones ambiguas que requieren confirmación humana."""
        reviews = repository.list_pending_reviews(provider_id)
        return {"count": len(reviews), "reviews": list(reviews)}

    @server.tool()
    def confirm_product_match(
        provider_id: str,
        canonical_product_id: str,
        supplier_product_id: str,
        run_id: str,
        idempotency_key: str,
    ) -> dict[str, str]:
        """Confirma explícitamente una asociación humana de producto."""
        repository.record_confirmed_mapping(
            provider_id,
            canonical_product_id,
            supplier_product_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
        )
        return {"status": "confirmed", "providerId": provider_id, "canonicalProductId": canonical_product_id}

    @server.tool()
    def generate_machine_supplier_report(
        provider_id: str,
        machine_products: list[dict[str, Any]],
        matches: list[dict[str, Any]],
        run_id: str,
    ) -> dict[str, str]:
        """Genera el XLSX por máquina/proveedor usando exclusivamente MachinePrice como PVP."""
        request = GenerateMachineSupplierReportRequestV1.model_validate(
            {
                "providerId": provider_id,
                "machineProducts": machine_products,
                "matches": matches,
                "runId": run_id,
            }
        )
        path = repository.generate_machine_supplier_report(
            request.provider_id,
            request.machine_products,
            request.matches,
            request.run_id,
        )
        return {"providerId": request.provider_id, "reportPath": str(path), "runId": request.run_id}

    @server.tool()
    def assess_legacy_name_mappings(provider_id: str, mappings: list[dict[str, Any]]) -> dict[str, Any]:
        """Evalúa mappings YAML antiguos en modo informe, sin guardarlos ni confirmarlos."""
        request = LegacyMappingReportRequestV1.model_validate({"providerId": provider_id, "mappings": mappings})
        results = repository.assess_legacy_name_mappings(
            request.provider_id,
            tuple((mapping.nayax_product_name, mapping.supplier_product_id) for mapping in request.mappings),
        )
        return {
            "providerId": request.provider_id,
            "persisted": False,
            "results": [
                {
                    "supplierProductId": result.supplier_product_id,
                    "status": result.status,
                    "method": result.method,
                    "confidence": result.confidence,
                    "reason": result.reason,
                }
                for result in results
            ],
        }

    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
