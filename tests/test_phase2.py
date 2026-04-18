"""Phase 2 tests: agents module.

All Anthropic API calls are mocked — no network required.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from empathy.agents.base import _MAX_FEEDBACK_DRAFTS, BaseAgent
from empathy.agents.client import ClientAgent
from empathy.agents.therapist import TherapistAgent
from empathy.core.models import Draft, Turn, TurnSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_anthropic(response_text: str) -> MagicMock:
    """Return a mock anthropic.Anthropic client that yields response_text via speak tool."""
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "speak"
    mock_block.input = {"content": response_text}

    mock_message = MagicMock()
    mock_message.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    return mock_client


def _make_agent(side: str = "therapist", **kwargs: object) -> BaseAgent:
    agent = BaseAgent(side=side, **kwargs)  # type: ignore[arg-type]
    agent._client = _mock_anthropic("I hear you.")
    return agent


def _turn(speaker: str, content: str, source: TurnSource = TurnSource.HUMAN) -> Turn:
    return Turn.create(speaker=speaker, source=source, content=content)  # type: ignore[arg-type]


def _draft(speaker: str, content: str, outcome: str, final: str | None = None) -> Draft:
    d = Draft.create(speaker=speaker, content=content, source_instruction="x")  # type: ignore[arg-type]
    d.outcome = outcome  # type: ignore[assignment]
    d.final_content = final
    return d


# ---------------------------------------------------------------------------
# _build_system
# ---------------------------------------------------------------------------


def test_build_system_minimal() -> None:
    agent = _make_agent()
    blocks = agent._build_system()
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert "therapist" in blocks[0]["text"]


def test_build_system_with_background() -> None:
    agent = _make_agent(dialogue_background="Scene: job loss")
    blocks = agent._build_system()
    assert len(blocks) == 2
    assert "cache_control" in blocks[1]
    assert blocks[1]["cache_control"] == {"type": "ephemeral"}
    assert "job loss" in blocks[1]["text"]


def test_build_system_with_knowledge() -> None:
    agent = _make_agent(knowledge="Use Socratic questioning.")
    blocks = agent._build_system()
    assert len(blocks) == 2
    assert "cache_control" in blocks[1]
    assert "Socratic" in blocks[1]["text"]


def test_build_system_background_and_knowledge() -> None:
    agent = _make_agent(dialogue_background="Scene", knowledge="Guidelines")
    blocks = agent._build_system()
    assert len(blocks) == 3
    # Both stable blocks should be cached
    assert all("cache_control" in b for b in blocks[1:])


# ---------------------------------------------------------------------------
# _build_messages
# ---------------------------------------------------------------------------


def test_build_messages_empty_transcript() -> None:
    agent = _make_agent()
    msgs = agent._build_messages([], [], "Start the session")
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert "Start the session" in msgs[0]["content"]


def test_build_messages_first_message_always_user() -> None:
    """If transcript starts with agent's own turn, prefix with '(dialogue begins)'."""
    agent = _make_agent(side="therapist")
    turns = [_turn("therapist", "Hello, what brings you here?")]
    msgs = agent._build_messages(turns, [], "Continue")
    assert msgs[0]["role"] == "user"
    assert "(dialogue begins)" in msgs[0]["content"]


def test_build_messages_normal_alternating() -> None:
    agent = _make_agent(side="therapist")
    turns = [
        _turn("therapist", "Hello"),
        _turn("client", "I feel anxious"),
    ]
    msgs = agent._build_messages(turns, [], "Explore the anxiety")
    # therapist=assistant, client=user → first is assistant → "(dialogue begins)" inserted
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "Hello"
    assert msgs[2]["role"] == "user"
    assert "I feel anxious" in msgs[2]["content"]
    # instruction is merged into the last user message
    assert "Explore the anxiety" in msgs[2]["content"]


def test_build_messages_consecutive_same_role_merged() -> None:
    agent = _make_agent(side="therapist")
    # Two consecutive client turns (client holds floor for multi-turn)
    turns = [
        _turn("client", "I've been stressed."),
        _turn("client", "It started last week."),
    ]
    msgs = agent._build_messages(turns, [], "Reflect back")
    # Both client turns → user role → merged
    user_msgs = [m for m in msgs if m["role"] == "user"]
    combined = " ".join(m["content"] for m in user_msgs)
    assert "stressed" in combined
    assert "last week" in combined


def test_build_messages_instruction_in_final_user_turn() -> None:
    agent = _make_agent(side="therapist")
    msgs = agent._build_messages([], [], "Ask about childhood")
    assert "Ask about childhood" in msgs[-1]["content"]
    assert msgs[-1]["role"] == "user"


# ---------------------------------------------------------------------------
# _format_feedback
# ---------------------------------------------------------------------------


def test_format_feedback_empty() -> None:
    agent = _make_agent()
    assert agent._format_feedback([]) == ""


def test_format_feedback_only_accepted_drafts_ignored() -> None:
    agent = _make_agent(side="therapist")
    history = [_draft("therapist", "Good response", "accepted")]
    assert agent._format_feedback(history) == ""


def test_format_feedback_rejected_shown() -> None:
    agent = _make_agent(side="therapist")
    history = [_draft("therapist", "Bad response", "rejected")]
    result = agent._format_feedback(history)
    assert "REJECTED" in result
    assert "Bad response" in result


def test_format_feedback_edited_shows_diff() -> None:
    agent = _make_agent(side="therapist")
    history = [_draft("therapist", "original text", "edited", final="improved text")]
    result = agent._format_feedback(history)
    assert "EDITED" in result
    assert "original text" in result
    assert "improved text" in result


def test_format_feedback_other_side_ignored() -> None:
    """Feedback for the other side should not appear."""
    agent = _make_agent(side="therapist")
    history = [_draft("client", "client rejected draft", "rejected")]
    assert agent._format_feedback(history) == ""


def test_format_feedback_max_limit() -> None:
    agent = _make_agent(side="therapist")
    history = [_draft("therapist", f"draft {i}", "rejected") for i in range(20)]
    result = agent._format_feedback(history)
    # Should mention at most _MAX_FEEDBACK_DRAFTS items
    assert result.count("REJECTED") <= _MAX_FEEDBACK_DRAFTS


# ---------------------------------------------------------------------------
# generate_draft
# ---------------------------------------------------------------------------


def test_generate_draft_returns_stripped_text() -> None:
    agent = _make_agent()
    agent._client = _mock_anthropic("  Hello there.  \n")
    result = agent.generate_draft("Say hello", [])
    assert result.content == "Hello there."
    assert result.type == "draft"


def test_generate_draft_calls_api_with_correct_model() -> None:
    agent = _make_agent()
    mock_client = _mock_anthropic("response")
    agent._client = mock_client

    agent.generate_draft("Greet", [])

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == agent.model
    assert call_kwargs["max_tokens"] == agent.max_tokens


def test_generate_draft_passes_system_and_messages() -> None:
    agent = _make_agent(knowledge="Use CBT")
    mock_client = _mock_anthropic("response")
    agent._client = mock_client

    agent.generate_draft("Ask about mood", [_turn("client", "I feel sad")])

    call_kwargs = mock_client.messages.create.call_args.kwargs
    system = call_kwargs["system"]
    messages = call_kwargs["messages"]
    assert isinstance(system, list)
    assert any("CBT" in b["text"] for b in system)
    assert any("sad" in m["content"] for m in messages)


def test_generate_draft_raises_on_non_text_block() -> None:
    # When the API returns only tool_use blocks (no text) and no tools are
    # configured, the loop should exhaust its retries and raise ValueError.
    agent = _make_agent()
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_message = MagicMock()
    mock_message.content = [mock_block]
    agent._client = MagicMock()
    agent._client.messages.create.return_value = mock_message

    with pytest.raises(ValueError, match="exceeded"):
        agent.generate_draft("Say something", [])


# ---------------------------------------------------------------------------
# TherapistAgent / ClientAgent
# ---------------------------------------------------------------------------


def test_therapist_agent_side() -> None:
    agent = TherapistAgent()
    agent._client = _mock_anthropic("response")
    assert agent.side == "therapist"
    assert "therapist" in agent._role_preamble()


def test_client_agent_side() -> None:
    agent = ClientAgent()
    agent._client = _mock_anthropic("response")
    assert agent.side == "client"
    assert "client" in agent._role_preamble()


def test_therapist_agent_custom_model() -> None:
    agent = TherapistAgent(model="claude-opus-4-6")
    assert agent.model == "claude-opus-4-6"


def test_client_agent_generate() -> None:
    agent = ClientAgent(knowledge="Express mild anxiety")
    agent._client = _mock_anthropic("I've been feeling on edge lately.")
    result = agent.generate_draft(
        "Describe your anxiety",
        [_turn("therapist", "What brings you here?")],
    )
    assert result.content == "I've been feeling on edge lately."
