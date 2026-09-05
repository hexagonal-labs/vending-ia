from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from supplier_bridge.application.contracts import CostPolicyV1, SupplierOfferSnapshotV1, SupplierOfferV1
from supplier_bridge.infrastructure.config import Settings
from supplier_bridge.infrastructure.distribuidora_mayorista import DistribuidoraMayoristaClient


def create_server(settings: Settings | None = None) -> FastMCP:
    current_settings = settings or Settings()
    client = DistribuidoraMayoristaClient(
        current_settings.distribuidora_mayorista_base_url,
        current_settings.distribuidora_mayorista_email,
        current_settings.distribuidora_mayorista_password,
        current_settings.distribuidora_mayorista_wishlist_id,
        current_settings.distribuidora_mayorista_cost_policy(),
    )
    server = FastMCP(
        "supplier-bridge",
        instructions=(
            "Consulta proveedores externos y devuelve ofertas normalizadas. "
            "No consulta Nayax, no hace matching y no escribe el catálogo Excel."
        ),
    )

    @server.tool()
    def list_suppliers() -> dict[str, Any]:
        """Lista los proveedores API habilitados y su política de coste explícita."""
        policy = CostPolicyV1.from_domain(client.cost_policy()).model_dump(mode="json", by_alias=True)
        return {
            "suppliers": [
                {
                    "supplierId": client.provider_id,
                    "name": "Distribuidora Mayorista",
                    "costPolicy": policy,
                }
            ]
        }

    @server.tool()
    async def fetch_supplier_offers(supplier_id: str) -> dict[str, Any]:
        """Obtiene un snapshot fechado de las ofertas actuales del proveedor solicitado."""
        _ensure_supported_supplier(supplier_id, client.provider_id)
        snapshot = SupplierOfferSnapshotV1.from_domain(await client.fetch_snapshot())
        return {
            "snapshot": snapshot.model_dump(mode="json", by_alias=True),
            "costPolicy": CostPolicyV1.from_domain(client.cost_policy()).model_dump(mode="json", by_alias=True),
        }

    @server.tool()
    async def get_supplier_offer(supplier_id: str, supplier_sku: str) -> dict[str, Any]:
        """Busca una oferta actual por SKU de proveedor dentro de un snapshot recién consultado."""
        _ensure_supported_supplier(supplier_id, client.provider_id)
        snapshot = await client.fetch_snapshot()
        offer = next((product for product in snapshot.products if product.supplier_product_id == supplier_sku), None)
        if offer is None:
            raise ValueError(f"No existe la oferta {supplier_sku} en {supplier_id}")
        return {
            "providerId": supplier_id,
            "retrievedAt": snapshot.retrieved_at.isoformat(),
            "offer": SupplierOfferV1.from_domain(offer).model_dump(mode="json", by_alias=True),
            "costPolicy": CostPolicyV1.from_domain(client.cost_policy()).model_dump(mode="json", by_alias=True),
        }

    return server


def _ensure_supported_supplier(supplier_id: str, expected_supplier_id: str) -> None:
    if supplier_id != expected_supplier_id:
        raise ValueError(f"Proveedor no disponible: {supplier_id}")


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
