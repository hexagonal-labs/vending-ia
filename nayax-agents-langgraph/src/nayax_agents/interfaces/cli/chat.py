from __future__ import annotations

import argparse
import asyncio
from typing import Any

from nayax_agents.graphs.info_graph import build_info_graph
from nayax_agents.infrastructure.checkpointer import open_sqlite_checkpointer
from nayax_agents.infrastructure.config import Settings
from nayax_agents.infrastructure.llm import build_chat_model
from nayax_agents.infrastructure.mcp import build_nayax_mcp_client, load_info_tools
from nayax_agents.infrastructure.messages import message_content_text


async def run_chat(thread_id: str) -> None:
    settings = Settings()
    model = build_chat_model(settings)
    client = build_nayax_mcp_client(settings.nayax_bridge_dir, settings.nayax_node_command)
    tools = await load_info_tools(client)
    if not tools:
        raise RuntimeError("El servidor MCP no expone ninguna tool de información")

    async with open_sqlite_checkpointer(settings.nayax_checkpoint_db) as checkpointer:
        graph = build_info_graph(model, tools, checkpointer)
        print(f"nayax-agents-langgraph · thread={thread_id} · /exit para salir")

        while True:
            question = input("\n> ").strip()
            if question.lower() in {"/exit", "/quit", "salir"}:
                return
            if not question:
                continue

            result: Any = await graph.ainvoke(
                {"messages": [{"role": "user", "content": question}]},
                config={"configurable": {"thread_id": thread_id}},
            )
            messages = result.get("messages", [])
            final_message = messages[-1] if messages else None
            print(message_content_text(final_message or "Sin respuesta"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat de información Nayax con LangGraph")
    parser.add_argument("--thread-id", default="cli-default", help="Identificador persistente de la conversación")
    args = parser.parse_args()
    try:
        asyncio.run(run_chat(args.thread_id))
    except KeyboardInterrupt:
        print("\nSesión terminada.")
    except Exception as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
