from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from nayax_agents.domain import NayaxMachine, NayaxProduct, SupplierProduct


class NayaxCatalogPort(Protocol):
    async def list_machines(self) -> Sequence[NayaxMachine]: ...

    async def list_machine_products(self, machine_id: int) -> Sequence[NayaxProduct]: ...


class SupplierCatalogPort(Protocol):
    @property
    def provider_id(self) -> str: ...

    async def fetch_products(self) -> Sequence[SupplierProduct]: ...


class AgentRunnerPort(Protocol):
    async def invoke(self, conversation_id: str, question: str) -> str: ...


class NotifierPort(Protocol):
    async def send(self, text: str) -> None: ...


@dataclass(frozen=True, slots=True)
class MarginReportDependencies:
    nayax_catalog: NayaxCatalogPort
    supplier_catalog: SupplierCatalogPort
    agent_runner: AgentRunnerPort
    notifier: NotifierPort
