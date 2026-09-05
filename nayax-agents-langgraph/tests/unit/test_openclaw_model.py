from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from nayax_agents.infrastructure.openclaw_model import OpenClawToolProtocolModel


class FakeGatewayModel:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[Any] = []

    async def ainvoke(self, messages: list[Any], **_: Any) -> AIMessage:
        self.messages = messages
        return AIMessage(content=self.content)


def fake_tool(name: str = "list_machines") -> Any:
    return SimpleNamespace(
        name=name,
        description="Lista las máquinas Nayax",
        args={"type": "object", "properties": {}},
    )


@pytest.mark.asyncio
async def test_translates_openclaw_tool_call_into_langgraph_tool_call() -> None:
    gateway = FakeGatewayModel('{"type":"tool_call","name":"list_machines","arguments":{}}')
    model = OpenClawToolProtocolModel(gateway).bind_tools([fake_tool()])

    result = await model.ainvoke([HumanMessage(content="Lista las máquinas")])

    assert result.tool_calls[0]["name"] == "list_machines"
    assert result.tool_calls[0]["args"] == {}
    assert gateway.messages[0].type == "system"
    assert "Nunca ejecutes herramientas" in gateway.messages[0].content


@pytest.mark.asyncio
async def test_translates_openclaw_final_response() -> None:
    gateway = FakeGatewayModel('{"type":"final","content":"Hay 3 máquinas."}')
    model = OpenClawToolProtocolModel(gateway).bind_tools([fake_tool()])

    result = await model.ainvoke([HumanMessage(content="¿Cuántas hay?")])

    assert result.content == "Hay 3 máquinas."
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_keeps_raw_model_behavior_without_tools() -> None:
    gateway = FakeGatewayModel("texto libre")
    model = OpenClawToolProtocolModel(gateway)

    result = await model.ainvoke([HumanMessage(content="Redacta un informe")])

    assert result.content == "texto libre"


def test_rejects_tool_not_exposed_by_langgraph() -> None:
    model = OpenClawToolProtocolModel(FakeGatewayModel("irrelevant"), [fake_tool()])

    with pytest.raises(ValueError, match="no disponible"):
        model._parse_response('{"type":"tool_call","name":"delete_machine","arguments":{}}')
