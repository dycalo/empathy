"""Integration tests for training data export functionality.

Tests the complete workflow from dialogue creation through export.
"""

import json
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from empathy.core.models import Draft, Turn, TurnSource
from empathy.storage.drafts import append_draft
from empathy.storage.transcript import append_turn
from empathy.utils.export import TrainingDataExporter


def test_full_export_workflow():
    """Test complete workflow: create dialogue → generate drafts → export training data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dialogue_dir = Path(tmpdir) / "test_session"
        dialogue_dir.mkdir()

        transcript_path = dialogue_dir / "transcript.jsonl"
        draft_history_path = dialogue_dir / "draft-history.jsonl"

        # Simulate a dialogue session
        # Turn 1: Client speaks (human input)
        turn1 = Turn.create(
            speaker="client",
            content="I've been feeling really anxious lately.",
            source=TurnSource.HUMAN,
        )
        append_turn(transcript_path, turn1)

        # Turn 2: Therapist generates draft (accepted)
        draft2 = Draft(
            id=str(uuid.uuid4()),
            speaker="therapist",
            content="Thank you for sharing that. Can you tell me more?",
            source_instruction="acknowledge and explore",
            outcome="accepted",
            timestamp=datetime.now(UTC),
            conversation_window={"start_turn": 0, "end_turn": 0},
            api_usage={
                "input_tokens": 500,
                "output_tokens": 50,
                "cached_tokens": 200,
                "latency_ms": 1500,
            },
            model="claude-haiku-4-5-20251001",
        )
        append_draft(draft_history_path, draft2)

        turn2 = Turn.create(
            speaker="therapist",
            content=draft2.content,
            source=TurnSource.AGENT_ACCEPT,
            draft_id=draft2.id,
        )
        append_turn(transcript_path, turn2)

        # Turn 3: Client speaks (human input)
        turn3 = Turn.create(
            speaker="client",
            content="It happens before big meetings. My heart races.",
            source=TurnSource.HUMAN,
        )
        append_turn(transcript_path, turn3)

        # Turn 4: Therapist generates draft (rejected)
        draft4_rejected = Draft(
            id=str(uuid.uuid4()),
            speaker="therapist",
            content="Let's talk about your childhood experiences with failure.",
            source_instruction="explore the anxiety",
            outcome="rejected",
            timestamp=datetime.now(UTC),
            conversation_window={"start_turn": 0, "end_turn": 2},
            api_usage={
                "input_tokens": 800,
                "output_tokens": 60,
                "cached_tokens": 400,
                "latency_ms": 2000,
            },
            rejection_reason="too directive, jumped to conclusions",
            model="claude-haiku-4-5-20251001",
        )
        append_draft(draft_history_path, draft4_rejected)

        # Turn 4: Therapist generates new draft (accepted)
        draft4_accepted = Draft(
            id=str(uuid.uuid4()),
            speaker="therapist",
            content="I notice you mentioned your heart racing. What else do you feel physically?",
            source_instruction="explore the anxiety",
            outcome="accepted",
            timestamp=datetime.now(UTC),
            conversation_window={"start_turn": 0, "end_turn": 2},
            api_usage={
                "input_tokens": 850,
                "output_tokens": 55,
                "cached_tokens": 450,
                "latency_ms": 1800,
            },
            model="claude-haiku-4-5-20251001",
        )
        append_draft(draft_history_path, draft4_accepted)

        turn4 = Turn.create(
            speaker="therapist",
            content=draft4_accepted.content,
            source=TurnSource.AGENT_ACCEPT,
            draft_id=draft4_accepted.id,
        )
        append_turn(transcript_path, turn4)

        # Turn 5: Client speaks (human input)
        turn5 = Turn.create(
            speaker="client",
            content="My chest feels tight and I start sweating.",
            source=TurnSource.HUMAN,
        )
        append_turn(transcript_path, turn5)

        # Turn 6: Therapist generates draft (edited)
        draft6 = Draft(
            id=str(uuid.uuid4()),
            speaker="therapist",
            content="That sounds difficult.",
            source_instruction="validate their feelings",
            outcome="edited",
            timestamp=datetime.now(UTC),
            final_content="That sounds really challenging. I hear the distress in what you're describing.",
            conversation_window={"start_turn": 1, "end_turn": 4},
            api_usage={
                "input_tokens": 900,
                "output_tokens": 40,
                "cached_tokens": 500,
                "latency_ms": 1600,
            },
            model="claude-haiku-4-5-20251001",
        )
        append_draft(draft_history_path, draft6)

        turn6 = Turn.create(
            speaker="therapist",
            content=draft6.final_content,
            source=TurnSource.AGENT_EDIT,
            draft_id=draft6.id,
            original_draft=draft6.content,
        )
        append_turn(transcript_path, turn6)

        # Now export the data
        exporter = TrainingDataExporter(dialogue_dir)

        # Test SFT export
        sft_output = Path(tmpdir) / "test_session_sft.jsonl"
        sft_stats = exporter.export(sft_output, format="sft")

        assert sft_stats.sft_samples == 3  # turns 2, 4, 6 (all therapist agent turns)
        assert sft_stats.total_turns == 6
        assert sft_output.exists()

        # Verify SFT samples
        with sft_output.open("r") as f:
            sft_samples = [json.loads(line) for line in f]

        assert len(sft_samples) == 3

        # Check first SFT sample (turn 2)
        sample1 = sft_samples[0]
        assert sample1["completion"] == "Thank you for sharing that. Can you tell me more?"
        assert sample1["prompt"]["instruction"] == "acknowledge and explore"
        assert sample1["metadata"]["source"] == "accepted"
        assert sample1["metadata"]["model"] == "claude-haiku-4-5-20251001"

        # Check edited SFT sample (turn 6)
        sample3 = sft_samples[2]
        assert sample3["completion"] == "That sounds really challenging. I hear the distress in what you're describing."
        assert sample3["metadata"]["source"] == "edited"

        # Test RLHF export
        rlhf_output = Path(tmpdir) / "test_session_rlhf.jsonl"
        rlhf_stats = exporter.export(rlhf_output, format="rlhf", include_types=["rejected", "edited"])

        assert rlhf_stats.rlhf_samples == 2  # 1 rejected + 1 edited
        assert rlhf_stats.rejected_drafts == 1
        assert rlhf_stats.edited_drafts == 1
        assert rlhf_output.exists()

        # Verify RLHF samples
        with rlhf_output.open("r") as f:
            rlhf_samples = [json.loads(line) for line in f]

        assert len(rlhf_samples) == 2

        # Check rejected RLHF sample
        rejected_sample = next(s for s in rlhf_samples if s["metadata"]["chosen_source"] == "accepted")
        assert rejected_sample["chosen"] == "I notice you mentioned your heart racing. What else do you feel physically?"
        assert rejected_sample["rejected"] == "Let's talk about your childhood experiences with failure."
        assert rejected_sample["feedback_label"] is None
        assert rejected_sample["metadata"]["rejection_reason"] == "too directive, jumped to conclusions"

        # Check edited RLHF sample
        edited_sample = next(s for s in rlhf_samples if s["metadata"]["chosen_source"] == "edited")
        assert edited_sample["chosen"] == "That sounds really challenging. I hear the distress in what you're describing."
        assert edited_sample["rejected"] == "That sounds difficult."
        assert edited_sample["feedback_label"] is None


def test_export_with_only_rejected():
    """Test RLHF export with only rejected drafts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dialogue_dir = Path(tmpdir) / "test_session"
        dialogue_dir.mkdir()

        transcript_path = dialogue_dir / "transcript.jsonl"
        draft_history_path = dialogue_dir / "draft-history.jsonl"

        # Create minimal dialogue with rejected draft
        turn1 = Turn.create(speaker="client", content="I'm anxious.", source=TurnSource.HUMAN)
        append_turn(transcript_path, turn1)

        draft_rejected = Draft(
            id=str(uuid.uuid4()),
            speaker="therapist",
            content="Bad response.",
            source_instruction="help",
            outcome="rejected",
            timestamp=datetime.now(UTC),
            conversation_window={"start_turn": 0, "end_turn": 0},
            model="claude-haiku-4-5-20251001",
        )
        append_draft(draft_history_path, draft_rejected)

        draft_accepted = Draft(
            id=str(uuid.uuid4()),
            speaker="therapist",
            content="Good response.",
            source_instruction="help",
            outcome="accepted",
            timestamp=datetime.now(UTC),
            conversation_window={"start_turn": 0, "end_turn": 0},
            model="claude-haiku-4-5-20251001",
        )
        append_draft(draft_history_path, draft_accepted)

        turn2 = Turn.create(
            speaker="therapist",
            content="Good response.",
            source=TurnSource.AGENT_ACCEPT,
            draft_id=draft_accepted.id,
        )
        append_turn(transcript_path, turn2)

        # Export with only rejected
        exporter = TrainingDataExporter(dialogue_dir)
        output = Path(tmpdir) / "test_session_rlhf.jsonl"
        stats = exporter.export(output, format="rlhf", include_types=["rejected"])

        assert stats.rlhf_samples == 1

        with output.open("r") as f:
            samples = [json.loads(line) for line in f]

        assert len(samples) == 1
        assert samples[0]["rejected"] == "Bad response."
        assert samples[0]["chosen"] == "Good response."


def test_export_with_only_edited():
    """Test RLHF export with only edited drafts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dialogue_dir = Path(tmpdir) / "test_session"
        dialogue_dir.mkdir()

        transcript_path = dialogue_dir / "transcript.jsonl"
        draft_history_path = dialogue_dir / "draft-history.jsonl"

        # Create minimal dialogue with edited draft
        turn1 = Turn.create(speaker="client", content="I'm sad.", source=TurnSource.HUMAN)
        append_turn(transcript_path, turn1)

        draft_edited = Draft(
            id=str(uuid.uuid4()),
            speaker="therapist",
            content="Original.",
            source_instruction="respond",
            outcome="edited",
            timestamp=datetime.now(UTC),
            final_content="Edited version.",
            conversation_window={"start_turn": 0, "end_turn": 0},
            model="claude-haiku-4-5-20251001",
        )
        append_draft(draft_history_path, draft_edited)

        turn2 = Turn.create(
            speaker="therapist",
            content="Edited version.",
            source=TurnSource.AGENT_EDIT,
            draft_id=draft_edited.id,
            original_draft="Original.",
        )
        append_turn(transcript_path, turn2)

        # Export with only edited
        exporter = TrainingDataExporter(dialogue_dir)
        output = Path(tmpdir) / "test_session_rlhf.jsonl"
        stats = exporter.export(output, format="rlhf", include_types=["edited"])

        assert stats.rlhf_samples == 1
        assert stats.edited_drafts == 1

        with output.open("r") as f:
            samples = [json.loads(line) for line in f]

        assert len(samples) == 1
        assert samples[0]["rejected"] == "Original."
        assert samples[0]["chosen"] == "Edited version."


def test_export_empty_dialogue():
    """Test export with empty dialogue."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dialogue_dir = Path(tmpdir) / "empty_session"
        dialogue_dir.mkdir()

        exporter = TrainingDataExporter(dialogue_dir)

        # Export SFT
        sft_output = Path(tmpdir) / "test_session_sft.jsonl"
        sft_stats = exporter.export(sft_output, format="sft")

        assert sft_stats.sft_samples == 0
        assert sft_stats.total_turns == 0
        assert sft_output.exists()

        # Export RLHF
        rlhf_output = Path(tmpdir) / "test_session_rlhf.jsonl"
        rlhf_stats = exporter.export(rlhf_output, format="rlhf")

        assert rlhf_stats.rlhf_samples == 0
        assert rlhf_stats.rejected_drafts == 0
        assert rlhf_stats.edited_drafts == 0
        assert rlhf_output.exists()


if __name__ == "__main__":
    print("Running integration tests...")

    print("\n1. Testing full export workflow...")
    test_full_export_workflow()
    print("✓ Full workflow test passed")

    print("\n2. Testing export with only rejected...")
    test_export_with_only_rejected()
    print("✓ Rejected-only test passed")

    print("\n3. Testing export with only edited...")
    test_export_with_only_edited()
    print("✓ Edited-only test passed")

    print("\n4. Testing export with empty dialogue...")
    test_export_empty_dialogue()
    print("✓ Empty dialogue test passed")

    print("\n✅ All integration tests passed!")
