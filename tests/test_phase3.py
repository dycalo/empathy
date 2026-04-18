"""Phase 3 tests: DialogueSession and Textual confirmation UI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from empathy.agents.base import BaseAgent
from empathy.cli.confirm import ConfirmApp, ConfirmResult
from empathy.cli.repl import _handle_command
from empathy.core.models import TurnSource
from empathy.modes.session import DialogueSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_agent(response: str = "Agent reply", is_draft: bool = True) -> BaseAgent:
    agent = BaseAgent(side="therapist")
    agent._client = MagicMock()

    if is_draft:
        block = MagicMock()
        block.type = "tool_use"
        block.name = "speak"
        block.input = {"content": response}
    else:
        block = MagicMock()
        block.type = "text"
        block.text = response

    agent._client.messages.create.return_value = MagicMock(content=[block])
    return agent


def _session(
    tmp_path: Path,
    side: str = "therapist",
    response: str = "Agent reply",
) -> DialogueSession:
    dialogue_dir = tmp_path / "dialogue"
    dialogue_dir.mkdir()
    return DialogueSession(
        dialogue_dir=dialogue_dir,
        side=side,  # type: ignore[arg-type]
        agent=_mock_agent(response),
    )


# ---------------------------------------------------------------------------
# DialogueSession — paths
# ---------------------------------------------------------------------------


def test_session_paths(tmp_path: Path) -> None:
    s = _session(tmp_path)
    assert s.transcript_path == s.dialogue_dir / "transcript.jsonl"
    assert s.drafts_path == s.dialogue_dir / "draft-history.jsonl"
    assert s.state_path == s.dialogue_dir / ".empathy" / "state.json"


# ---------------------------------------------------------------------------
# DialogueSession — floor
# ---------------------------------------------------------------------------


def test_session_acquire_and_release_floor(tmp_path: Path) -> None:
    s = _session(tmp_path)
    assert s.try_acquire_floor() is True
    assert s.floor_status()["floor_holder"] == "therapist"
    s.release_floor()
    assert s.floor_status()["floor_holder"] is None


def test_session_floor_blocked_by_other_side(tmp_path: Path) -> None:
    s_therapist = _session(tmp_path, side="therapist")
    s_client = DialogueSession(
        dialogue_dir=s_therapist.dialogue_dir,
        side="client",
        agent=_mock_agent(),
    )
    s_therapist.try_acquire_floor()
    assert s_client.try_acquire_floor() is False


# ---------------------------------------------------------------------------
# DialogueSession — generate_draft
# ---------------------------------------------------------------------------


def test_generate_draft_creates_pending_draft(tmp_path: Path) -> None:
    s = _session(tmp_path, response="You seem anxious.")
    draft = s.generate_draft("reflect back")
    assert draft.content == "You seem anxious."
    assert draft.outcome == "pending"
    assert draft.speaker == "therapist"

    persisted = s.get_draft_history()
    assert len(persisted) == 1
    assert persisted[0].id == draft.id


# ---------------------------------------------------------------------------
# DialogueSession — accept_draft
# ---------------------------------------------------------------------------


def test_accept_draft_commits_to_transcript(tmp_path: Path) -> None:
    s = _session(tmp_path, response="Good insight.")
    draft = s.generate_draft("acknowledge")

    turn = s.accept_draft(draft)

    assert turn.source is TurnSource.AGENT_ACCEPT
    assert turn.content == "Good insight."
    assert turn.draft_id == draft.id
    assert turn.original_draft is None

    turns = s.get_transcript()
    assert len(turns) == 1
    assert turns[0].id == turn.id

    updated = s.get_draft_history()[0]
    assert updated.outcome == "accepted"


# ---------------------------------------------------------------------------
# DialogueSession — edit_draft
# ---------------------------------------------------------------------------


def test_edit_draft_preserves_original(tmp_path: Path) -> None:
    s = _session(tmp_path, response="Original text.")
    draft = s.generate_draft("say something")

    turn = s.edit_draft(draft, "Improved text.")

    assert turn.source is TurnSource.AGENT_EDIT
    assert turn.content == "Improved text."
    assert turn.original_draft == "Original text."
    assert turn.draft_id == draft.id

    updated = s.get_draft_history()[0]
    assert updated.outcome == "edited"
    assert updated.final_content == "Improved text."


# ---------------------------------------------------------------------------
# DialogueSession — reject_draft
# ---------------------------------------------------------------------------


def test_reject_draft_not_in_transcript(tmp_path: Path) -> None:
    s = _session(tmp_path, response="Bad response.")
    draft = s.generate_draft("say something")

    s.reject_draft(draft)

    assert s.get_transcript() == []
    assert s.get_draft_history()[0].outcome == "rejected"


# ---------------------------------------------------------------------------
# DialogueSession — commit_human_turn
# ---------------------------------------------------------------------------


def test_commit_human_turn(tmp_path: Path) -> None:
    s = _session(tmp_path)
    turn = s.commit_human_turn("Hello, I'm the therapist.")

    assert turn.source is TurnSource.HUMAN
    assert turn.content == "Hello, I'm the therapist."
    assert turn.draft_id is None

    turns = s.get_transcript()
    assert len(turns) == 1


# ---------------------------------------------------------------------------
# DialogueSession — full workflow
# ---------------------------------------------------------------------------


def test_full_workflow_accept_then_reject(tmp_path: Path) -> None:
    s = _session(tmp_path, response="Draft A")
    d1 = s.generate_draft("instruction 1")
    s.accept_draft(d1)

    s2 = DialogueSession(
        dialogue_dir=s.dialogue_dir,
        side="therapist",
        agent=_mock_agent("Draft B"),
    )
    d2 = s2.generate_draft("instruction 2")
    s2.reject_draft(d2)

    assert len(s.get_transcript()) == 1
    history = s.get_draft_history()
    assert len(history) == 2
    assert history[0].outcome == "accepted"
    assert history[1].outcome == "rejected"


# ---------------------------------------------------------------------------
# ConfirmResult
# ---------------------------------------------------------------------------


def test_confirm_result_defaults() -> None:
    r = ConfirmResult(action="accept")
    assert r.edited_content is None


def test_confirm_result_edit() -> None:
    r = ConfirmResult(action="edit", edited_content="new text")
    assert r.action == "edit"
    assert r.edited_content == "new text"


# ---------------------------------------------------------------------------
# ConfirmApp — Textual tests (async, no real terminal)
# ---------------------------------------------------------------------------


async def test_confirm_app_accept() -> None:
    app = ConfirmApp("Test draft")
    async with app.run_test() as pilot:
        await pilot.press("a")
    assert app.return_value is not None
    assert app.return_value.action == "accept"


async def test_confirm_app_reject() -> None:
    app = ConfirmApp("Test draft")
    async with app.run_test() as pilot:
        await pilot.press("r")
    assert app.return_value is not None
    assert app.return_value.action == "reject"


async def test_confirm_app_human() -> None:
    app = ConfirmApp("Test draft")
    async with app.run_test() as pilot:
        await pilot.press("h")
    assert app.return_value is not None
    assert app.return_value.action == "human"


async def test_confirm_app_edit_flow() -> None:
    """Press e to enter edit mode, then ctrl+s to save (draft text unchanged)."""
    app = ConfirmApp("Original draft")
    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()  # wait for TextArea to mount
        await pilot.press("ctrl+s")
    assert app.return_value is not None
    assert app.return_value.action == "edit"
    assert app.return_value.edited_content == "Original draft"


async def test_confirm_app_cancel_edit_returns_to_draft() -> None:
    app = ConfirmApp("Original draft")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("a")
    assert app.return_value is not None
    assert app.return_value.action == "accept"


# ---------------------------------------------------------------------------
# _handle_command (repl.py)
# ---------------------------------------------------------------------------


def test_handle_command_quit(tmp_path: Path) -> None:
    s = _session(tmp_path)
    s.try_acquire_floor()
    result = _handle_command("/quit", s)
    assert result is True
    assert s.floor_status()["floor_holder"] is None


def test_handle_command_done(tmp_path: Path) -> None:
    s = _session(tmp_path)
    s.try_acquire_floor()
    result = _handle_command("/done", s)
    assert result is False
    assert s.floor_status()["floor_holder"] is None


def test_handle_command_unknown(tmp_path: Path) -> None:
    s = _session(tmp_path)
    result = _handle_command("/bogus", s)
    assert result is False
