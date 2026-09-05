from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from langgraph_sdk.runtime import ServerRuntime

from nayax_agents.application.catalog_pricing_workflow import CatalogPricingWorkflow
from nayax_agents.graphs.info_graph import build_info_graph
from nayax_agents.graphs.pricing_graph import build_catalog_pricing_graph
from nayax_agents.infrastructure.config import Settings
from nayax_agents.infrastructure.llm import build_chat_model
from nayax_agents.infrastructure.mcp import (
    build_nayax_mcp_client,
    build_pricing_mcp_client,
    group_pricing_tools,
    load_info_tools,
)


@asynccontextmanager
async def make_info_graph(runtime: ServerRuntime[Any]) -> AsyncIterator[Any]:
    """Factory para Studio: carga MCP solo al ejecutar una conversación."""
    settings = Settings()
    model = build_chat_model(settings)
    tools: list[Any] = []

    if runtime.execution_runtime is not None:
        client = build_nayax_mcp_client(settings.nayax_bridge_dir, settings.nayax_node_command)
        tools = await load_info_tools(client)

    yield build_info_graph(model, tools)


@asynccontextmanager
async def make_pricing_graph(runtime: ServerRuntime[Any]) -> AsyncIterator[Any]:
    """Factory para Studio del workflow de márgenes."""
    settings = Settings()
    if runtime.execution_runtime is None:
        yield build_catalog_pricing_graph(
            CatalogPricingWorkflow({}, {}, {}),
            default_supplier_id=settings.pricing_default_provider_id,
            default_provider_source=settings.pricing_default_provider_source,
        )
        return
    client = build_pricing_mcp_client(
        nayax_bridge_dir=settings.nayax_bridge_dir,
        supplier_bridge_dir=settings.supplier_bridge_dir,
        pricing_catalog_bridge_dir=settings.pricing_catalog_bridge_dir,
        invoice_bridge_dir=settings.invoice_bridge_dir,
        nayax_node_command=settings.nayax_node_command,
        python_command=settings.bridge_python_command,
        pricing_data_dir=settings.pricing_data_dir,
    )
    grouped = group_pricing_tools(await client.get_tools())
    yield build_catalog_pricing_graph(
        CatalogPricingWorkflow(grouped["nayax"], grouped["supplier"], grouped["pricing_catalog"]),
        default_supplier_id=settings.pricing_default_provider_id,
        default_provider_source=settings.pricing_default_provider_source,
    )
