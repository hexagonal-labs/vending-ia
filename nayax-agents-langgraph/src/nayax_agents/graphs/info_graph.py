from __future__ import annotations

from pathlib import Path
from typing import Any

from nayax_agents.graphs.state import NayaxGraphState

INFO_SYSTEM_PROMPT = (Path(__file__).parents[1] / "prompts" / "info_agent.md").read_text(encoding="utf-8")


def build_info_graph(
    model: Any,
    tools: list[Any],
    checkpointer: Any = None,
) -> Any:
    """Construye el grafo de información y mantiene las tools en LangGraph."""
    from langchain_core.messages import SystemMessage
    from langgraph.graph import END, START, StateGraph

    model_with_tools = model.bind_tools(tools)

    async def call_model(state: NayaxGraphState) -> dict[str, list[Any]]:
        response = await model_with_tools.ainvoke([SystemMessage(content=INFO_SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [response]}

    graph = StateGraph(NayaxGraphState)
    graph.add_node("LLM", call_model)
    graph.add_edge(START, "LLM")
    from langgraph.prebuilt import ToolNode, tools_condition

    graph.add_node("NAYAX_API", ToolNode(tools))
    graph.add_conditional_edges("LLM", tools_condition, {"tools": "NAYAX_API", END: END})
    graph.add_edge("NAYAX_API", "LLM")
    return graph.compile(checkpointer=checkpointer)
