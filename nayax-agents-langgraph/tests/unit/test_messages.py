from __future__ import annotations

from langchain_core.messages import AIMessage

from nayax_agents.infrastructure.messages import message_content_text


def test_message_content_text_keeps_plain_text() -> None:
    assert message_content_text(AIMessage(content="respuesta")) == "respuesta"


def test_message_content_text_flattens_responses_blocks() -> None:
    message = AIMessage(
        content=[
            {"type": "text", "text": "primera"},
            {"type": "text", "text": "segunda"},
        ]
    )

    assert message_content_text(message) == "primera\nsegunda"
