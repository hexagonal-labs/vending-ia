from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any


@asynccontextmanager
async def open_sqlite_checkpointer(path: Path) -> AsyncIterator[Any]:
    """Abre el checkpointer SQLite y mantiene viva la conexión durante el grafo."""
    import aiosqlite
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    path.parent.mkdir(parents=True, exist_ok=True)
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("nayax_agents.domain.models", "NayaxMachine"),
            ("nayax_agents.domain.models", "NayaxPrices"),
            ("nayax_agents.domain.models", "NayaxProduct"),
            ("nayax_agents.domain.models", "SupplierProduct"),
            ("nayax_agents.domain.models", "ProductMapping"),
            ("nayax_agents.domain.margin_report", "MarginRow"),
            ("nayax_agents.domain.margin_report", "MatchMarginsResult"),
        ]
    )
    async with aiosqlite.connect(str(path)) as connection:
        saver = AsyncSqliteSaver(connection, serde=serde)
        await saver.setup()
        yield saver
