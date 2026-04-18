"""Phase 1 tests: core models, storage, extensions."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from empathy.core.models import DialogueMeta, Draft, Turn, TurnSource
from empathy.extensions.config import _deep_merge, load_config
from empathy.extensions.psych import load_dialogue_background, load_side_knowledge
from empathy.storage import drafts as drafts_store
from empathy.storage import state as state_store
from empathy.storage import transcript as transcript_store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tmp(tmp_path: Path, name: str) -> Path:
    return tmp_path / name


# ---------------------------------------------------------------------------
# TurnSource
# ---------------------------------------------------------------------------


def test_turnsource_values() -> None:
    assert TurnSource.HUMAN.value == "human"
    assert TurnSource.AGENT_AUTO.value == "agent_auto"
    assert TurnSource.AGENT_ACCEPT.value == "agent_accept"
    assert TurnSource.AGENT_EDIT.value == "agent_edit"
    assert TurnSource.AGENT_REJECT.value == "agent_reject"


def test_turnsource_from_string() -> None:
    assert TurnSource("human") is TurnSource.HUMAN
    assert TurnSource("agent_edit") is TurnSource.AGENT_EDIT


# ---------------------------------------------------------------------------
# Turn
# ---------------------------------------------------------------------------


def test_turn_create_defaults() -> None:
    t = Turn.create(speaker="therapist", source=TurnSource.HUMAN, content="Hello")
    assert t.speaker == "therapist"
    assert t.source is TurnSource.HUMAN
    assert t.content == "Hello"
    assert t.draft_id is None
    assert t.original_draft is None
    assert t.annotations == {}
    assert len(t.id) == 36  # UUID


def test_turn_roundtrip() -> None:
    t = Turn.create(
        speaker="client",
        source=TurnSource.AGENT_EDIT,
        content="final text",
        draft_id="draft-123",
        original_draft="original text",
        annotations={"tag": "important"},
    )
    restored = Turn.from_dict(t.to_dict())
    assert restored.id == t.id
    assert restored.speaker == t.speaker
    assert restored.source is t.source
    assert restored.content == t.content
    assert restored.timestamp == t.timestamp
    assert restored.draft_id == t.draft_id
    assert restored.original_draft == t.original_draft
    assert restored.annotations == t.annotations


def test_turn_to_dict_source_is_string() -> None:
    t = Turn.create(speaker="therapist", source=TurnSource.AGENT_AUTO, content="x")
    assert t.to_dict()["source"] == "agent_auto"


# ---------------------------------------------------------------------------
# Draft
# ---------------------------------------------------------------------------


def test_draft_create_defaults() -> None:
    d = Draft.create(speaker="therapist", content="draft text", source_instruction="be empathetic")
    assert d.outcome == "pending"
    assert d.final_content is None
    assert d.hook_annotations == {}


def test_draft_roundtrip() -> None:
    d = Draft.create(
        speaker="client",
        content="I feel anxious",
        source_instruction="describe anxiety",
        hook_annotations={"score": 0.9},
    )
    restored = Draft.from_dict(d.to_dict())
    assert restored.id == d.id
    assert restored.speaker == d.speaker
    assert restored.content == d.content
    assert restored.source_instruction == d.source_instruction
    assert restored.outcome == d.outcome
    assert restored.timestamp == d.timestamp
    assert restored.hook_annotations == d.hook_annotations


# ---------------------------------------------------------------------------
# DialogueMeta
# ---------------------------------------------------------------------------


def test_dialogue_meta_roundtrip() -> None:
    from datetime import datetime

    meta = DialogueMeta(
        id="session_20260417_a1b2",
        path="dialogues/session_20260417_a1b2",
        status="active",
        created_at=datetime(2026, 4, 17, 10, 0, 0),
        sides_connected=["therapist"],
    )
    restored = DialogueMeta.from_dict(meta.to_dict())
    assert restored.id == meta.id
    assert restored.status == meta.status
    assert restored.sides_connected == ["therapist"]


# ---------------------------------------------------------------------------
# storage/transcript.py
# ---------------------------------------------------------------------------


def test_transcript_append_and_read(tmp_path: Path) -> None:
    path = _tmp(tmp_path, "transcript.jsonl")
    t1 = Turn.create("therapist", TurnSource.HUMAN, "Hello")
    t2 = Turn.create("client", TurnSource.AGENT_ACCEPT, "Hi there")

    transcript_store.append_turn(path, t1)
    transcript_store.append_turn(path, t2)

    turns = transcript_store.read_turns(path)
    assert len(turns) == 2
    assert turns[0].id == t1.id
    assert turns[1].content == "Hi there"
    assert turns[1].source is TurnSource.AGENT_ACCEPT


def test_transcript_read_missing_file(tmp_path: Path) -> None:
    turns = transcript_store.read_turns(tmp_path / "nonexistent.jsonl")
    assert turns == []


def test_transcript_is_valid_jsonl(tmp_path: Path) -> None:
    path = _tmp(tmp_path, "transcript.jsonl")
    for i in range(3):
        transcript_store.append_turn(path, Turn.create("therapist", TurnSource.HUMAN, f"msg {i}"))
    lines = path.read_text().splitlines()
    assert len(lines) == 3
    for line in lines:
        obj = json.loads(line)
        assert "id" in obj and "content" in obj


# ---------------------------------------------------------------------------
# storage/drafts.py
# ---------------------------------------------------------------------------


def test_drafts_append_and_read(tmp_path: Path) -> None:
    path = _tmp(tmp_path, "draft-history.jsonl")
    d = Draft.create("therapist", "draft text", "instruction")

    drafts_store.append_draft(path, d)
    loaded = drafts_store.read_drafts(path)

    assert len(loaded) == 1
    assert loaded[0].id == d.id
    assert loaded[0].outcome == "pending"


def test_drafts_update_outcome(tmp_path: Path) -> None:
    path = _tmp(tmp_path, "draft-history.jsonl")
    d = Draft.create("client", "response", "write a response")
    drafts_store.append_draft(path, d)

    drafts_store.update_draft_outcome(path, d.id, "edited", final_content="edited response")

    loaded = drafts_store.read_drafts(path)
    assert loaded[0].outcome == "edited"
    assert loaded[0].final_content == "edited response"


def test_drafts_update_rejected(tmp_path: Path) -> None:
    path = _tmp(tmp_path, "draft-history.jsonl")
    d = Draft.create("therapist", "bad draft", "say something")
    drafts_store.append_draft(path, d)

    drafts_store.update_draft_outcome(path, d.id, "rejected")

    loaded = drafts_store.read_drafts(path)
    assert loaded[0].outcome == "rejected"
    assert loaded[0].final_content is None


def test_drafts_read_missing_file(tmp_path: Path) -> None:
    assert drafts_store.read_drafts(tmp_path / "nonexistent.jsonl") == []


# ---------------------------------------------------------------------------
# storage/state.py
# ---------------------------------------------------------------------------


def test_state_defaults(tmp_path: Path) -> None:
    state = state_store.read_state(tmp_path / "state.json")
    assert state["floor_holder"] is None
    assert state["turn_number"] == 0


def test_acquire_and_release_floor(tmp_path: Path) -> None:
    path = _tmp(tmp_path, "state.json")

    assert state_store.acquire_floor(path, "therapist") is True
    state = state_store.read_state(path)
    assert state["floor_holder"] == "therapist"

    state_store.release_floor(path, "therapist")
    state = state_store.read_state(path)
    assert state["floor_holder"] is None
    assert state["last_speaker"] == "therapist"
    assert state["turn_number"] == 1


def test_acquire_floor_blocked_by_other_side(tmp_path: Path) -> None:
    path = _tmp(tmp_path, "state.json")

    state_store.acquire_floor(path, "therapist")
    result = state_store.acquire_floor(path, "client")
    assert result is False


def test_acquire_own_floor_is_idempotent(tmp_path: Path) -> None:
    path = _tmp(tmp_path, "state.json")

    assert state_store.acquire_floor(path, "therapist") is True
    assert state_store.acquire_floor(path, "therapist") is True  # re-acquiring own floor


def test_floor_not_timed_out_fresh(tmp_path: Path) -> None:
    path = _tmp(tmp_path, "state.json")
    state_store.acquire_floor(path, "therapist")
    assert state_store.is_floor_timed_out(path) is False


def test_floor_timeout_detection(tmp_path: Path) -> None:
    path = _tmp(tmp_path, "state.json")
    # Manually write a state with floor_since far in the past
    state = {
        "turn_number": 0,
        "floor_holder": "client",
        "floor_since": time.time() - 999,
        "last_speaker": None,
        "floor_timeout_seconds": 300,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    tmp.rename(path)
    assert state_store.is_floor_timed_out(path) is True


# ---------------------------------------------------------------------------
# extensions/config.py
# ---------------------------------------------------------------------------


def test_deep_merge_simple() -> None:
    base = {"a": 1, "b": {"x": 1, "y": 2}}
    override = {"b": {"y": 99, "z": 3}, "c": 4}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": {"x": 1, "y": 99, "z": 3}, "c": 4}


def test_deep_merge_override_wins_scalar() -> None:
    result = _deep_merge({"a": 1}, {"a": 2})
    assert result["a"] == 2


def test_load_config_all_missing(tmp_path: Path) -> None:
    cfg = load_config("therapist", global_dir=tmp_path)
    assert cfg == {}


def test_load_config_global_only(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("llm:\n  model: claude-opus\n")
    cfg = load_config("therapist", global_dir=tmp_path)
    assert cfg["llm"]["model"] == "claude-opus"


def test_load_config_three_tier_merge(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    (global_dir / "config.yaml").write_text("llm:\n  model: base\n  temp: 0.7\n")

    user_dir = global_dir / "users" / "user123"
    user_dir.mkdir(parents=True)
    (user_dir / "config.yaml").write_text("llm:\n  model: overridden\n")

    dialogue_dir = tmp_path / "dialogue"
    dialogue_dir.mkdir(parents=True)
    (dialogue_dir / "dialogue.yaml").write_text(
        "therapist_id: user123\nllm:\n  temp: 0.3\nfloor_timeout_seconds: 600\n"
    )

    cfg = load_config(
        "therapist",
        dialogue_dir=dialogue_dir,
        global_dir=global_dir,
    )
    assert cfg["llm"]["model"] == "overridden"  # user overrides global
    assert cfg["llm"]["temp"] == pytest.approx(0.3)  # dialogue overrides user
    assert cfg["floor_timeout_seconds"] == 600


# ---------------------------------------------------------------------------
# extensions/psych.py
# ---------------------------------------------------------------------------


def test_load_side_knowledge_empty(tmp_path: Path) -> None:
    result = load_side_knowledge("therapist", global_dir=tmp_path)
    assert result == ""


def test_load_side_knowledge_global_only(tmp_path: Path) -> None:
    (tmp_path / "therapist").mkdir()
    (tmp_path / "therapist" / "THERAPIST.md").write_text("# Global therapist knowledge")
    result = load_side_knowledge("therapist", global_dir=tmp_path)
    assert "<global_state>\n# Global therapist knowledge\n</global_state>" in result


def test_load_side_knowledge_dialogue_first(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    (global_dir / "therapist").mkdir()
    (global_dir / "therapist" / "THERAPIST.md").write_text("global knowledge")

    dialogue_dir = tmp_path / "dialogue"
    (dialogue_dir / "therapist").mkdir(parents=True)
    (dialogue_dir / "therapist" / "THERAPIST.md").write_text("dialogue knowledge")

    result = load_side_knowledge("therapist", dialogue_dir=dialogue_dir, global_dir=global_dir)
    assert "<dialogue_state>\ndialogue knowledge\n</dialogue_state>" in result
    assert "<global_state>\nglobal knowledge\n</global_state>" in result


def test_load_client_knowledge(tmp_path: Path) -> None:
    (tmp_path / "client").mkdir()
    (tmp_path / "client" / "CLIENT.md").write_text("# Global client profile")
    result = load_side_knowledge("client", global_dir=tmp_path)
    assert "<global_state>\n# Global client profile\n</global_state>" in result


def test_load_dialogue_background_missing(tmp_path: Path) -> None:
    assert load_dialogue_background(tmp_path) == ""


def test_load_dialogue_background(tmp_path: Path) -> None:
    empathy_dir = tmp_path / ".empathy"
    empathy_dir.mkdir()
    (empathy_dir / "DIALOGUE.md").write_text("# Scene: job loss counseling")
    result = load_dialogue_background(tmp_path)
    assert "job loss counseling" in result
