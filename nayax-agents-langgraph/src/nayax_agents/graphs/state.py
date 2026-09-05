from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from langgraph.graph import MessagesState

from nayax_agents.domain import MatchMarginsResult, NayaxMachine, NayaxProduct, ProductMapping, SupplierProduct


class NayaxGraphState(MessagesState, total=False):
    thread_id: str
    user_question: str
    intent: Literal["info", "pricing", "unsupported"]
    machines: Sequence[NayaxMachine]
    nayax_products: Sequence[NayaxProduct]
    supplier_products: Sequence[SupplierProduct]
    mappings: Sequence[ProductMapping]
    margin_result: MatchMarginsResult
    raw_report: str
    final_reply: str
    error: str
    status: Literal["running", "waiting", "completed", "failed"]
