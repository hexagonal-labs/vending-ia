"""Orquestación determinista del pricing a través de los MCP especializados."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from nayax_agents.infrastructure.nayax_catalog import McpNayaxCatalog


class CatalogPricingWorkflow:
    """El núcleo coordina Nayax, proveedores y catálogo sin acoplar sus SDK."""

    def __init__(
        self,
        nayax_tools: Mapping[str, Any],
        supplier_tools: Mapping[str, Any],
        catalog_tools: Mapping[str, Any],
    ) -> None:
        self._nayax = McpNayaxCatalog(nayax_tools)
        self._supplier_tools = supplier_tools
        self._catalog_tools = catalog_tools

    async def run(
        self,
        supplier_id: str,
        *,
        provider_source: Literal["api", "catalog"] = "api",
        max_machine_fetch_concurrency: int = 4,
    ) -> dict[str, Any]:
        if max_machine_fetch_concurrency < 1:
            raise ValueError("max_machine_fetch_concurrency debe ser mayor que cero")
        if not supplier_id.strip():
            raise ValueError("supplier_id es obligatorio")
        run_id = datetime.now(UTC).strftime("pricing-%Y%m%dT%H%M%SZ")
        if provider_source == "api":
            supplier_response = _mapping(
                await _invoke(self._supplier_tools, "fetch_supplier_offers", {"supplier_id": supplier_id})
            )
            snapshot = _mapping(supplier_response.get("snapshot"))
            snapshot_key = _key("snapshot", snapshot)
            await _invoke(
                self._catalog_tools,
                "record_supplier_snapshot",
                {"snapshot": snapshot, "idempotency_key": snapshot_key},
            )
        elif provider_source != "catalog":
            raise ValueError("provider_source debe ser 'api' o 'catalog'")

        machines = await self._nayax.list_machines()
        semaphore = asyncio.Semaphore(max_machine_fetch_concurrency)

        async def fetch(machine_id: int) -> list[Any]:
            async with semaphore:
                return await self._nayax.list_machine_products(machine_id)

        batches = await asyncio.gather(*(fetch(machine.machine_id) for machine in machines))
        machine_products: list[dict[str, Any]] = []
        vending_products: dict[str, dict[str, Any]] = {}
        for machine, products in zip(machines, batches, strict=True):
            for product in products:
                canonical_id = (
                    f"nayax:{product.nayax_product_id}"
                    if product.nayax_product_id is not None
                    else f"nayax:unresolved:{machine.machine_id}:{product.machine_product_id}"
                )
                machine_products.append(
                    {
                        "machineId": str(machine.machine_id),
                        "machineName": machine.name,
                        "selection": product.machine_product_id,
                        "canonicalProductId": canonical_id,
                        "productName": product.name,
                        "machinePrice": str(product.prices.machine) if product.prices.machine is not None else None,
                    }
                )
                if product.nayax_product_id is not None:
                    vending_products.setdefault(
                        canonical_id,
                        {
                            "canonicalProductId": canonical_id,
                            "productName": product.name,
                            "ean": product.ean,
                        },
                    )
        matching = _mapping(
            await _invoke(
                self._catalog_tools,
                "match_products",
                {
                    "provider_id": supplier_id,
                    "vending_products": list(vending_products.values()),
                    "run_id": run_id,
                    "idempotency_key": _key("matching", {"run": run_id, "products": vending_products}),
                },
            )
        )
        matches = list(matching.get("matches", []))
        matches_by_id = {str(item["canonicalProductId"]): item for item in matches if isinstance(item, Mapping)}
        # Los productos sin NayaxProductID nunca se asocian automáticamente, pero aparecen en Excel.
        for product in machine_products:
            canonical_id = str(product["canonicalProductId"])
            if canonical_id not in matches_by_id:
                matches.append(
                    {
                        "canonicalProductId": canonical_id,
                        "supplierProductId": None,
                        "status": "SOURCE_INCOMPLETE",
                        "method": "none",
                        "confidence": 0.0,
                        "reason": "El producto de máquina no incluye NayaxProductID.",
                    }
                )
                matches_by_id[canonical_id] = matches[-1]

        reports: list[str] = []
        by_machine: dict[str, list[dict[str, Any]]] = {}
        for product in machine_products:
            by_machine.setdefault(str(product["machineId"]), []).append(product)
        for machine_id, products in by_machine.items():
            result = _mapping(
                await _invoke(
                    self._catalog_tools,
                    "generate_machine_supplier_report",
                    {
                        "provider_id": supplier_id,
                        "machine_products": products,
                        "matches": matches,
                        "run_id": f"{run_id}-{machine_id}",
                    },
                )
            )
            reports.append(str(result["reportPath"]))
        return {
            "runId": run_id,
            "supplierId": supplier_id,
            "providerSource": provider_source,
            "machineCount": len(machines),
            "productCount": len(machine_products),
            "matchedCount": sum(1 for match in matches if str(match.get("status", "")).startswith("MATCHED")),
            "reviewCount": sum(1 for match in matches if match.get("status") == "PENDING_REVIEW"),
            "unmatchedCount": sum(1 for match in matches if not str(match.get("status", "")).startswith("MATCHED")),
            "reports": reports,
        }

    async def run_all_catalogs(
        self,
        *,
        max_machine_fetch_concurrency: int = 4,
    ) -> dict[str, Any]:
        """Compara las máquinas con todos los proveedores que tienen catálogo vigente."""
        providers_response = _mapping(await _invoke(self._catalog_tools, "list_catalog_providers", {}))
        provider_ids = [
            str(provider_id) for provider_id in providers_response.get("providerIds", []) if str(provider_id).strip()
        ]
        if not provider_ids:
            raise RuntimeError("No hay proveedores con productos vigentes en el catálogo local.")

        results = [
            await self.run(
                provider_id,
                provider_source="catalog",
                max_machine_fetch_concurrency=max_machine_fetch_concurrency,
            )
            for provider_id in provider_ids
        ]
        return {
            "providerSource": "catalog",
            "providerCount": len(results),
            "providers": results,
            "machineCount": max((int(result["machineCount"]) for result in results), default=0),
            "productCount": max((int(result["productCount"]) for result in results), default=0),
            "matchedCount": sum(int(result["matchedCount"]) for result in results),
            "reviewCount": sum(int(result["reviewCount"]) for result in results),
            "unmatchedCount": sum(int(result["unmatchedCount"]) for result in results),
            "reports": [report for result in results for report in result["reports"]],
        }


async def _invoke(tools: Mapping[str, Any], name: str, arguments: dict[str, Any]) -> Any:
    tool = tools.get(name)
    if tool is None:
        raise RuntimeError(f"La tool MCP requerida no está disponible: {name}")
    return await tool.ainvoke(arguments)


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        parsed = _parse_mcp_json(value)
        if isinstance(parsed, Mapping):
            return parsed
    if isinstance(value, list):
        text = "".join(str(item.get("text", "")) for item in value if isinstance(item, Mapping))
        if not text.strip():
            raise RuntimeError("La tool MCP devolvió una respuesta vacía; revisa el error del bridge en los logs.")
        parsed = _parse_mcp_json(text)
        if isinstance(parsed, Mapping):
            return parsed
    raise ValueError(f"Respuesta MCP no estructurada: {value!r}")


def _parse_mcp_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        excerpt = value.strip()[:500]
        raise ValueError(f"La tool MCP no devolvió JSON válido: {excerpt!r}") from error


def _key(prefix: str, value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:32]}"
