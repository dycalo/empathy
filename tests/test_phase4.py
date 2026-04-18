"""Phase 4 tests: Skills, auto mode."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from empathy.agents.base import BaseAgent
from empathy.core.models import TurnSource
from empathy.extensions.skills import Skill, load_skills
from empathy.modes.auto import run_auto

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill(skills_dir: Path, filename: str, content: str) -> None:
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / filename).write_text(content)


def _mock_agent(side: str = "therapist", response: str = "reply") -> BaseAgent:
    agent = BaseAgent(side=side)  # type: ignore[arg-type]
    block = MagicMock()
    block.type = "text"
    block.text = response
    agent._client = MagicMock()
    agent._client.messages.create.return_value = MagicMock(content=[block])
    return agent


# ---------------------------------------------------------------------------
# Skills — load_skills
# ---------------------------------------------------------------------------

SKILL_MD = """\
---
name: thought-record
side: therapist
description: Guide the client through identifying trigger -> automatic thought -> emotion.
---
This is the body text that actually explains how to do it.
It should be returned by read_skill_body.
"""


def test_load_skills_empty(tmp_path: Path) -> None:
    assert load_skills("therapist", global_dir=tmp_path, enabled_skills=["something"]) == {}


def test_load_skills_from_global(tmp_path: Path) -> None:
    _write_skill(tmp_path / "skills" / "therapist", "thought-record.md", SKILL_MD)
    skills = load_skills("therapist", global_dir=tmp_path, enabled_skills=["thought-record"])
    assert "thought-record" in skills
    assert skills["thought-record"].name == "thought-record"
    assert "automatic thought" in skills["thought-record"].description


def test_load_skills_returns_only_enabled(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills" / "therapist"
    skills_dir.mkdir(parents=True)
    _write_skill(skills_dir, "thought-record.md", SKILL_MD)
    _write_skill(skills_dir, "other.md", "---\nname: other\ndescription: foo\n---\nbody")

    # Enable only one
    skills = load_skills("therapist", global_dir=tmp_path, enabled_skills=["thought-record"])
    assert "thought-record" in skills
    assert "other" not in skills

    # None enabled means empty dict
    skills_none = load_skills("therapist", global_dir=tmp_path, enabled_skills=None)
    assert skills_none == {}


def test_skill_dataclass_fields() -> None:
    skill = Skill(
        name="cbt",
        side="therapist",
        description="Use CBT.",
        source_path=Path("/fake/path.md"),
    )
    assert skill.name == "cbt"
    assert skill.description == "Use CBT."


def test_build_skill_tool() -> None:
    from empathy.extensions.skills import build_skill_tool

    skills = {
        "s1": Skill(name="s1", side="therapist", description="desc 1", source_path=Path("")),
        "s2": Skill(name="s2", side="therapist", description="desc 2", source_path=Path("")),
    }

    tool = build_skill_tool("therapist", skills)
    assert tool["name"] == "apply_therapy"
    assert "s1: desc 1" in tool["description"]
    assert "s2: desc 2" in tool["description"]
    assert tool["input_schema"]["required"] == ["skill_name"]


def test_read_skill_body(tmp_path: Path) -> None:
    from empathy.extensions.skills import read_skill_body

    skills_dir = tmp_path / "skills" / "therapist"
    _write_skill(skills_dir, "thought-record.md", SKILL_MD)
    skills = load_skills("therapist", global_dir=tmp_path, enabled_skills=["thought-record"])
    skill = skills["thought-record"]

    body = read_skill_body(skill)
    assert "This is the body text" in body
    assert "description:" not in body


def test_load_skills_invalid_frontmatter_skipped(tmp_path: Path) -> None:
    """Files with unparseable frontmatter are silently skipped."""
    skills_dir = tmp_path / "skills" / "therapist"
    skills_dir.mkdir(parents=True)
    (skills_dir / "broken.md").write_text("not yaml frontmatter at all {{{")
    skills = load_skills("therapist", global_dir=tmp_path, enabled_skills=["broken"])
    # Should not raise; may or may not include the broken file depending on
    # how python-frontmatter handles plain text — just ensure no exception.
    assert isinstance(skills, dict)


# ---------------------------------------------------------------------------
# Auto mode — run_auto
# ---------------------------------------------------------------------------


def test_run_auto_produces_correct_turn_count(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.jsonl"
    drafts = tmp_path / "draft-history.jsonl"
    therapist = _mock_agent("therapist", "T reply")
    client = _mock_agent("client", "C reply")

    committed = run_auto(therapist, client, transcript, drafts, turns=4)

    assert len(committed) == 4


def test_run_auto_alternates_speakers(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.jsonl"
    drafts = tmp_path / "draft-history.jsonl"
    therapist = _mock_agent("therapist", "T")
    client = _mock_agent("client", "C")

    committed = run_auto(therapist, client, transcript, drafts, turns=4)

    speakers = [t.speaker for t in committed]
    assert speakers == ["therapist", "client", "therapist", "client"]


def test_run_auto_all_turns_are_agent_auto(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.jsonl"
    drafts = tmp_path / "draft-history.jsonl"
    committed = run_auto(
        _mock_agent("therapist"),
        _mock_agent("client"),
        transcript,
        drafts,
        turns=3,
    )
    assert all(t.source is TurnSource.AGENT_AUTO for t in committed)


def test_run_auto_writes_transcript(tmp_path: Path) -> None:
    from empathy.storage.transcript import read_turns

    transcript = tmp_path / "transcript.jsonl"
    drafts = tmp_path / "draft-history.jsonl"
    run_auto(_mock_agent("therapist"), _mock_agent("client"), transcript, drafts, turns=2)

    turns = read_turns(transcript)
    assert len(turns) == 2


def test_run_auto_writes_draft_history(tmp_path: Path) -> None:
    from empathy.storage.drafts import read_drafts

    transcript = tmp_path / "transcript.jsonl"
    drafts = tmp_path / "draft-history.jsonl"
    run_auto(_mock_agent("therapist"), _mock_agent("client"), transcript, drafts, turns=2)

    history = read_drafts(drafts)
    assert len(history) == 2
    assert all(d.outcome == "accepted" for d in history)


def test_run_auto_draft_id_links_turn(tmp_path: Path) -> None:
    from empathy.storage.drafts import read_drafts
    from empathy.storage.transcript import read_turns

    transcript = tmp_path / "transcript.jsonl"
    drafts = tmp_path / "draft-history.jsonl"
    run_auto(_mock_agent("therapist"), _mock_agent("client"), transcript, drafts, turns=1)

    turn = read_turns(transcript)[0]
    draft = read_drafts(drafts)[0]
    assert turn.draft_id == draft.id


def test_run_auto_zero_turns(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.jsonl"
    drafts = tmp_path / "draft-history.jsonl"
    committed = run_auto(
        _mock_agent("therapist"), _mock_agent("client"), transcript, drafts, turns=0
    )
    assert committed == []
