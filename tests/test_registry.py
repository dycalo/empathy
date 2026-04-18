"""Tests for storage/registry.py and end-to-end session initialization."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from empathy.agents.base import BaseAgent
from empathy.core.models import DialogueMeta
from empathy.modes.session import DialogueSession
from empathy.storage.registry import (
    create_dialogue,
    list_dialogues,
    register_dialogue,
    update_dialogue,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project(tmp_path: Path) -> Path:
    p = tmp_path / "project"
    p.mkdir()
    return p


def _meta(project_dir: Path, idx: int = 1) -> DialogueMeta:
    from datetime import UTC, datetime

    return DialogueMeta(
        id=f"session_test_{idx:04d}",
        path=f"dialogues/session_test_{idx:04d}",
        status="waiting",
        created_at=datetime.now(UTC),
        sides_connected=[],
    )


# ---------------------------------------------------------------------------
# list_dialogues — empty project
# ---------------------------------------------------------------------------


def test_list_dialogues_empty(tmp_path: Path) -> None:
    assert list_dialogues(_project(tmp_path)) == []


def test_list_dialogues_missing_empathy_dir(tmp_path: Path) -> None:
    """Project without .empathy/ should return empty list, not raise."""
    p = tmp_path / "bare"
    p.mkdir()
    assert list_dialogues(p) == []


# ---------------------------------------------------------------------------
# register_dialogue
# ---------------------------------------------------------------------------


def test_register_dialogue_creates_yaml(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    meta = _meta(proj, 1)
    register_dialogue(proj, meta)

    yaml_path = proj / ".empathy" / "dialogues.yaml"
    assert yaml_path.exists()


def test_register_dialogue_round_trip(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    meta = _meta(proj, 1)
    register_dialogue(proj, meta)

    loaded = list_dialogues(proj)
    assert len(loaded) == 1
    assert loaded[0].id == meta.id
    assert loaded[0].status == "waiting"
    assert loaded[0].sides_connected == []


def test_register_multiple_dialogues(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    for i in range(3):
        register_dialogue(proj, _meta(proj, i))
    assert len(list_dialogues(proj)) == 3


# ---------------------------------------------------------------------------
# update_dialogue
# ---------------------------------------------------------------------------


def test_update_dialogue_status(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    meta = _meta(proj, 1)
    register_dialogue(proj, meta)

    update_dialogue(proj, meta.id, status="active")

    loaded = list_dialogues(proj)
    assert loaded[0].status == "active"


def test_update_dialogue_sides_connected(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    meta = _meta(proj, 1)
    register_dialogue(proj, meta)

    update_dialogue(proj, meta.id, sides_connected=["therapist"])
    update_dialogue(proj, meta.id, sides_connected=["therapist", "client"], status="active")

    loaded = list_dialogues(proj)[0]
    assert loaded.sides_connected == ["therapist", "client"]
    assert loaded.status == "active"


def test_update_nonexistent_dialogue_is_noop(tmp_path: Path) -> None:
    """Updating a dialogue that doesn't exist should not raise."""
    proj = _project(tmp_path)
    meta = _meta(proj, 1)
    register_dialogue(proj, meta)

    update_dialogue(proj, "nonexistent_id", status="ended")

    # Original entry unchanged
    assert list_dialogues(proj)[0].status == "waiting"


# ---------------------------------------------------------------------------
# create_dialogue
# ---------------------------------------------------------------------------


def test_create_dialogue_registers_and_returns_path(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    meta, dialogue_dir = create_dialogue(proj)

    assert dialogue_dir.exists()
    assert (dialogue_dir / ".empathy").exists()
    assert (dialogue_dir / ".empathy" / "therapist").exists()
    assert (dialogue_dir / ".empathy" / "client").exists()

    registered = list_dialogues(proj)
    assert len(registered) == 1
    assert registered[0].id == meta.id
    assert registered[0].status == "waiting"


def test_create_dialogue_path_under_project(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    meta, dialogue_dir = create_dialogue(proj)

    assert dialogue_dir.parent.name == "dialogues"
    assert dialogue_dir.is_relative_to(proj)
    assert meta.path.startswith("dialogues/session_")


def test_create_dialogue_unique_ids(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    ids = {create_dialogue(proj)[0].id for _ in range(10)}
    assert len(ids) == 10


def test_create_dialogue_id_format(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    meta, _ = create_dialogue(proj)
    # Format: session_YYYYMMDD_XXXX
    parts = meta.id.split("_")
    assert parts[0] == "session"
    assert len(parts[1]) == 8 and parts[1].isdigit()
    assert len(parts[2]) == 4


# ---------------------------------------------------------------------------
# YAML datetime round-trip
# ---------------------------------------------------------------------------


def test_yaml_datetime_survives_reload(tmp_path: Path) -> None:
    """Ensure PyYAML auto-parsed datetimes are normalised back to str on load."""
    proj = _project(tmp_path)
    meta, _ = create_dialogue(proj)

    # Force a reload — PyYAML may parse the ISO string as a datetime object
    reloaded = list_dialogues(proj)
    assert reloaded[0].id == meta.id
    # created_at should be a proper datetime after from_dict()
    from datetime import datetime

    assert isinstance(reloaded[0].created_at, datetime)


# ---------------------------------------------------------------------------
# End-to-end: dialogue dir → DialogueSession (no real agent/LLM)
# ---------------------------------------------------------------------------


def _mock_agent() -> BaseAgent:
    agent = BaseAgent(side="therapist")
    block = MagicMock()
    block.type = "tool_use"
    block.name = "speak"
    block.input = {"content": "Mocked response."}
    agent._client = MagicMock()
    agent._client.messages.create.return_value = MagicMock(content=[block])
    return agent


def test_session_from_created_dialogue(tmp_path: Path) -> None:
    """create_dialogue → DialogueSession → full turn lifecycle."""
    proj = _project(tmp_path)
    _, dialogue_dir = create_dialogue(proj)

    session = DialogueSession(
        dialogue_dir=dialogue_dir,
        side="therapist",
        agent=_mock_agent(),
    )

    assert session.get_transcript() == []
    assert session.get_draft_history() == []

    # Human turn
    t = session.commit_human_turn("Hello")
    assert len(session.get_transcript()) == 1
    assert t.content == "Hello"

    # Agent draft → accept
    draft = session.generate_draft("reflect back")
    assert draft.content == "Mocked response."
    session.accept_draft(draft)
    assert len(session.get_transcript()) == 2


def test_session_config_loaded_from_dialogue_dir(tmp_path: Path) -> None:
    """Config from dialogue .empathy/config.yaml is visible via load_config."""
    from empathy.extensions.config import load_config

    proj = _project(tmp_path)
    _, dialogue_dir = create_dialogue(proj)

    (dialogue_dir / "dialogue.yaml").write_text("llm:\n  model: claude-opus-4-6\n")

    config = load_config("therapist", dialogue_dir=dialogue_dir)
    assert config["llm"]["model"] == "claude-opus-4-6"


def test_session_knowledge_loaded_from_dialogue_dir(tmp_path: Path) -> None:
    """PSYCH.md in dialogue .empathy/therapist/ is returned by load_side_knowledge."""
    from empathy.extensions.psych import load_side_knowledge

    proj = _project(tmp_path)
    _, dialogue_dir = create_dialogue(proj)

    (dialogue_dir / "therapist").mkdir(parents=True, exist_ok=True)
    (dialogue_dir / "therapist" / "THERAPIST.md").write_text(
        "# CBT framework\nUse Socratic questioning."
    )

    knowledge = load_side_knowledge("therapist", dialogue_dir=dialogue_dir)
    assert "Socratic" in knowledge
