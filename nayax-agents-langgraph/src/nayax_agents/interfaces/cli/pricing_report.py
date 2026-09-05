from __future__ import annotations

import argparse
import asyncio
import json
from typing import Literal, cast

from nayax_agents.application.catalog_pricing_workflow import CatalogPricingWorkflow
from nayax_agents.infrastructure.config import Settings
from nayax_agents.infrastructure.mcp import build_pricing_mcp_client, group_pricing_tools


async def run_pricing_report(provider_id: str | None, provider_source: Literal["api", "catalog"]) -> None:
    settings = Settings()
    client = build_pricing_mcp_client(
        nayax_bridge_dir=settings.nayax_bridge_dir,
        supplier_bridge_dir=settings.supplier_bridge_dir,
        pricing_catalog_bridge_dir=settings.pricing_catalog_bridge_dir,
        invoice_bridge_dir=settings.invoice_bridge_dir,
        nayax_node_command=settings.nayax_node_command,
        python_command=settings.bridge_python_command,
        pricing_data_dir=settings.pricing_data_dir,
        pricing_export_dir=settings.pricing_export_dir,
    )
    tools = await client.get_tools()
    grouped = group_pricing_tools(tools)
    workflow = CatalogPricingWorkflow(grouped["nayax"], grouped["supplier"], grouped["pricing_catalog"])
    if provider_id is None:
        if provider_source != "catalog":
            raise ValueError("--source api requiere --provider; para todos los catálogos usa --source catalog.")
        result = await workflow.run_all_catalogs(
            max_machine_fetch_concurrency=settings.max_machine_fetch_concurrency,
        )
    else:
        result = await workflow.run(
            provider_id,
            provider_source=provider_source,
            max_machine_fetch_concurrency=settings.max_machine_fetch_concurrency,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(description="Genera informes de margen por máquina y proveedor.")
    parser.add_argument(
        "--provider",
        default=settings.pricing_default_provider_id,
        help="Identificador del proveedor. Si se omite, compara todos los catálogos vigentes.",
    )
    parser.add_argument(
        "--source",
        choices=("api", "catalog"),
        default=settings.pricing_default_provider_source,
        help="api actualiza ofertas desde el proveedor; catalog usa precios ya importados.",
    )
    arguments = parser.parse_args()
    try:
        asyncio.run(run_pricing_report(arguments.provider, cast(Literal["api", "catalog"], arguments.source)))
    except KeyboardInterrupt:
        print("\nInforme cancelado.")
    except Exception as error:
        raise SystemExit(f"No se pudo generar el informe: {error}") from error


if __name__ == "__main__":
    main()
