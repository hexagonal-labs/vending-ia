from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from nayax_agents.application.contracts import NayaxMachineProductsResponseV1
from nayax_agents.domain import NayaxMachine, NayaxPrices, NayaxProduct


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, Mapping):
            return parsed
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        text_parts = [item.get("text", "") for item in value if isinstance(item, Mapping)]
        parsed = json.loads("".join(text_parts))
        if isinstance(parsed, Mapping):
            return parsed
    raise ValueError(f"Respuesta MCP no estructurada: {value!r}")


class McpNayaxCatalog:
    """Adaptador determinista sobre las tools MCP de lectura de nayax-bridge."""

    def __init__(self, tools: Mapping[str, Any]) -> None:
        self._tools = tools

    async def list_machines(self) -> list[NayaxMachine]:
        payload = _as_mapping(await self._call("list_machines", {}))
        return [
            NayaxMachine(machine_id=int(item["machineId"]), name=str(item.get("name", item["machineId"])))
            for item in payload.get("machines", [])
        ]

    async def list_machine_products(self, machine_id: int) -> list[NayaxProduct]:
        payload = _as_mapping(await self._call("list_machine_products", {"machineId": machine_id}))
        response = NayaxMachineProductsResponseV1.model_validate(payload)
        if response.machine_id != machine_id:
            raise ValueError(
                f"El bridge devolvió productos de la máquina {response.machine_id}, se pidió {machine_id}"
            )

        return [
            NayaxProduct(
                machine_id=item.machine_id,
                machine_product_id=item.machine_product_id,
                # ProductName es la fuente de verdad. name queda como fallback
                # para un producto que aún no tenga ficha de catálogo.
                name=_product_name(item.name, item.catalog_product.product_name if item.catalog_product else None),
                prices=NayaxPrices(machine=item.prices.machine, cash=item.prices.cash),
                nayax_product_id=item.nayax_product_id,
                ean=item.catalog_product.ean_code if item.catalog_product else None,
            )
            for item in response.products
        ]

    async def _call(self, name: str, arguments: Mapping[str, Any]) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise RuntimeError(f"La tool MCP requerida no está disponible: {name}")
        return await tool.ainvoke(dict(arguments))


def _product_name(name: str, catalog_product_name: str | None) -> str:
    if catalog_product_name and catalog_product_name.strip():
        return catalog_product_name.strip()
    return name.strip()
