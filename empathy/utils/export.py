"""Training data export utilities.

Exports dialogue data to training formats (SFT, RLHF) for model fine-tuning.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from empathy.core.models import Draft, Turn

logger = logging.getLogger(__name__)


@dataclass
class ExportStats:
    """Statistics for an export operation."""

    dialogue_id: str
    sft_samples: int = 0
    rlhf_samples: int = 0
    rejected_drafts: int = 0
    edited_drafts: int = 0
    total_turns: int = 0
    export_timestamp: str = ""


class TrainingDataExporter:
    """Exports dialogue data to training formats.

    Supports:
    - SFT (Supervised Fine-Tuning): from transcript.jsonl
    - RLHF (Reinforcement Learning from Human Feedback): from transcript + draft-history
    """

    def __init__(self, dialogue_dir: Path):
        """Initialize exporter.

        Args:
            dialogue_dir: Path to dialogue directory
        """
        self.dialogue_dir = dialogue_dir
        self.dialogue_id = dialogue_dir.name
        self.transcript_path = dialogue_dir / "transcript.jsonl"
        self.draft_history_path = dialogue_dir / "draft-history.jsonl"

    def load_data(self) -> tuple[list[Turn], list[Draft]]:
        """Load transcript and draft history.

        Returns:
            Tuple of (turns, drafts)
        """
        from empathy.storage.drafts import read_drafts
        from empathy.storage.transcript import read_turns

        turns = read_turns(self.transcript_path) if self.transcript_path.exists() else []
        drafts = read_drafts(self.draft_history_path) if self.draft_history_path.exists() else []

        return turns, drafts

    def build_system_prompt(self, side: str) -> str:
        """Build system prompt for the agent.

        Args:
            side: Speaker side ("therapist" or "client")

        Returns:
            System prompt string
        """
        other = "client" if side == "therapist" else "therapist"
        return (
            f"You are the {side} in a structured therapeutic dialogue "
            f"with a {other}. A human controller directs you via brief instructions."
        )

    def build_messages(
        self, turn: Turn, transcript: list[Turn], window_size: int = 6
    ) -> list[dict[str, str]]:
        """Build message history for a turn.

        Args:
            turn: Current turn
            transcript: Full transcript
            window_size: Number of previous turns to include

        Returns:
            List of message dicts with role and content
        """
        # Find turn index
        try:
            turn_index = next(i for i, t in enumerate(transcript) if t.id == turn.id)
        except StopIteration:
            return []

        # Get context window
        start_index = max(0, turn_index - window_size)
        context_turns = transcript[start_index:turn_index]

        messages = []
        for t in context_turns:
            role = "assistant" if t.speaker == turn.speaker else "user"
            messages.append({
                "role": role,
                "content": f"[{t.speaker.upper()}]: {t.content}",
            })

        return messages

    def build_messages_from_draft(
        self, draft: Draft, transcript: list[Turn], window_size: int = 6
    ) -> list[dict[str, str]]:
        """Build message history from draft's conversation window.

        Args:
            draft: Draft with conversation_window
            transcript: Full transcript
            window_size: Default window size if conversation_window not available

        Returns:
            List of message dicts with role and content
        """
        if draft.conversation_window:
            start = draft.conversation_window["start_turn"]
            end = draft.conversation_window["end_turn"]
            context_turns = transcript[start : end + 1]
        else:
            # Fallback to last N turns
            context_turns = transcript[-window_size:]

        messages = []
        for t in context_turns:
            role = "assistant" if t.speaker == draft.speaker else "user"
            messages.append({
                "role": role,
                "content": f"[{t.speaker.upper()}]: {t.content}",
            })

        return messages

    def build_sft_samples(self, turns: list[Turn], drafts: list[Draft]) -> list[dict[str, Any]]:
        """Build SFT training samples from transcript.

        Args:
            turns: Transcript turns
            drafts: Draft history (for source_instruction lookup)

        Returns:
            List of SFT samples
        """
        samples = []
        draft_map = {d.id: d for d in drafts}

        for turn in turns:
            # Only include agent-generated turns
            if turn.source.value not in ("agent_accept", "agent_edit"):
                continue

            # Find corresponding draft
            draft = draft_map.get(turn.draft_id) if turn.draft_id else None
            if not draft:
                logger.warning(f"No draft found for turn {turn.id}, skipping")
                continue

            # Build prompt
            system = self.build_system_prompt(turn.speaker)
            messages = self.build_messages(turn, turns)
            instruction = draft.source_instruction

            sample = {
                "prompt": {
                    "system": system,
                    "messages": messages,
                    "instruction": instruction,
                },
                "completion": turn.content,
                "metadata": {
                    "dialogue_id": self.dialogue_id,
                    "turn_number": turns.index(turn),
                    "turn_id": turn.id,
                    "timestamp": turn.timestamp.isoformat(),
                    "source": "edited" if turn.source.value == "agent_edit" else "accepted",
                    "model": getattr(draft, "model", None),
                },
            }
            samples.append(sample)

        return samples

    def build_rlhf_samples(
        self,
        turns: list[Turn],
        drafts: list[Draft],
        include_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Build RLHF training samples from transcript + draft history.

        Args:
            turns: Transcript turns
            drafts: Draft history
            include_types: Types to include ("rejected", "edited"), defaults to both

        Returns:
            List of RLHF samples
        """
        if include_types is None:
            include_types = ["rejected", "edited"]

        samples = []

        # Build turn lookup by speaker and approximate position
        turn_map: dict[tuple[str, int], Turn] = {}
        for i, turn in enumerate(turns):
            if turn.source.value in ("agent_accept", "agent_edit"):
                turn_map[(turn.speaker, i)] = turn

        for draft in drafts:
            # Skip if not in include_types
            if draft.outcome == "rejected" and "rejected" not in include_types:
                continue
            if draft.outcome == "edited" and "edited" not in include_types:
                continue
            if draft.outcome not in ("rejected", "edited"):
                continue

            # Find corresponding turn (chosen)
            chosen_turn = None
            if draft.outcome == "rejected":
                # Find next accepted turn from same speaker
                # Use conversation_window end as approximate position
                if draft.conversation_window:
                    approx_pos = draft.conversation_window["end_turn"] + 1
                    # Search nearby turns
                    for offset in range(5):  # Search next 5 turns
                        key = (draft.speaker, approx_pos + offset)
                        if key in turn_map:
                            chosen_turn = turn_map[key]
                            break
            elif draft.outcome == "edited":
                # For edited, the chosen is the final_content
                # We still need to find the turn for context
                for turn in turns:
                    if turn.draft_id == draft.id:
                        chosen_turn = turn
                        break

            if not chosen_turn:
                logger.warning(
                    f"No chosen turn found for draft {draft.id} (outcome={draft.outcome}), skipping"
                )
                continue

            # Build prompt
            system = self.build_system_prompt(draft.speaker)
            messages = self.build_messages_from_draft(draft, turns)
            instruction = draft.source_instruction

            # Determine chosen and rejected
            if draft.outcome == "rejected":
                chosen = chosen_turn.content
                rejected = draft.content
            else:  # edited
                chosen = draft.final_content or chosen_turn.content
                rejected = draft.content

            sample = {
                "prompt": {
                    "system": system,
                    "messages": messages,
                    "instruction": instruction,
                },
                "chosen": chosen,
                "rejected": rejected,
                "feedback_label": None,  # Reserved for future use
                "metadata": {
                    "dialogue_id": self.dialogue_id,
                    "turn_number": turns.index(chosen_turn) if chosen_turn in turns else -1,
                    "timestamp": draft.timestamp.isoformat(),
                    "chosen_source": "edited" if draft.outcome == "edited" else "accepted",
                    "rejected_draft_id": draft.id,
                    "rejection_reason": getattr(draft, "rejection_reason", None),
                    "model": getattr(draft, "model", None),
                },
            }
            samples.append(sample)

        return samples

    def export(
        self,
        output_path: Path,
        format: Literal["sft", "rlhf"] = "sft",
        include_types: list[str] | None = None,
    ) -> ExportStats:
        """Export training data to file.

        Args:
            output_path: Output file path (will append format suffix if needed)
            format: Export format ("sft" or "rlhf")
            include_types: For RLHF, types to include ("rejected", "edited")

        Returns:
            Export statistics
        """
        from datetime import UTC, datetime

        # Load data
        turns, drafts = self.load_data()

        # Build samples
        if format == "sft":
            samples = self.build_sft_samples(turns, drafts)
        else:  # rlhf
            samples = self.build_rlhf_samples(turns, drafts, include_types)

        # Ensure output path has correct suffix
        if not output_path.name.endswith(f"_{format}.jsonl"):
            output_path = output_path.parent / f"{output_path.stem}_{format}.jsonl"

        # Write samples
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

        # Build stats
        stats = ExportStats(
            dialogue_id=self.dialogue_id,
            sft_samples=len(samples) if format == "sft" else 0,
            rlhf_samples=len(samples) if format == "rlhf" else 0,
            rejected_drafts=sum(1 for d in drafts if d.outcome == "rejected"),
            edited_drafts=sum(1 for d in drafts if d.outcome == "edited"),
            total_turns=len(turns),
            export_timestamp=datetime.now(UTC).isoformat(),
        )

        logger.info(
            f"Exported {len(samples)} {format.upper()} samples to {output_path}"
        )

        return stats
