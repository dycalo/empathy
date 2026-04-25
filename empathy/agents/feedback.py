"""Feedback management for few-shot learning.

This module provides FeedbackManager for intelligent selection and formatting
of feedback examples from draft history.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class FeedbackConfig:
    """Configuration for feedback management."""

    max_examples: int = 5
    format_style: Literal["concise", "detailed"] = "concise"
    sampling_strategy: Literal["recent_only", "balanced", "relevant"] = "balanced"
    enable_rejection_reason: bool = False


class FeedbackManager:
    """Manages feedback examples for few-shot learning.

    Responsibilities:
    - Load feedback history from draft-history.jsonl
    - Intelligently select most relevant examples
    - Format examples for prompt injection
    """

    def __init__(self, dialogue_dir: Path | None = None, config: FeedbackConfig | None = None):
        """Initialize FeedbackManager.

        Args:
            dialogue_dir: Path to dialogue directory (optional if using direct history)
            config: Feedback configuration (uses defaults if None)
        """
        self.dialogue_dir = dialogue_dir
        self.config = config or FeedbackConfig()
        self.draft_history_path = dialogue_dir / "draft-history.jsonl" if dialogue_dir else None

    def load_feedback_history(
        self, side: str, max_items: int = 50
    ) -> list[dict]:
        """Load recent feedback history from draft-history.jsonl.

        Args:
            side: Speaker side ("therapist" or "client")
            max_items: Maximum number of items to load

        Returns:
            List of draft dictionaries (most recent first)
        """
        if not self.draft_history_path or not self.draft_history_path.exists():
            return []

        drafts = []
        try:
            with open(self.draft_history_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        draft = json.loads(line)
                        # Filter by side and only include rejected/edited
                        if (
                            draft.get("side") == side
                            and draft.get("result") in ["REJECT", "EDIT"]
                        ):
                            drafts.append(draft)
        except Exception as e:
            logger.error(f"Failed to load draft history: {e}")
            return []

        # Return most recent first, limited to max_items
        return list(reversed(drafts))[:max_items]

    def select_examples(
        self,
        history: list[dict],
        current_instruction: str,
        max_examples: int | None = None,
    ) -> list[dict]:
        """Intelligently select most relevant examples.

        Args:
            history: Full feedback history
            current_instruction: Current instruction (for relevance matching)
            max_examples: Maximum examples to select (uses config if None)

        Returns:
            Selected examples
        """
        if not history:
            return []

        max_examples = max_examples or self.config.max_examples

        if self.config.sampling_strategy == "recent_only":
            return self._select_recent(history, max_examples)
        elif self.config.sampling_strategy == "balanced":
            return self._select_balanced(history, max_examples)
        elif self.config.sampling_strategy == "relevant":
            return self._select_relevant(history, current_instruction, max_examples)
        else:
            return self._select_recent(history, max_examples)

    def _select_recent(self, history: list[dict], max_examples: int) -> list[dict]:
        """Select most recent examples."""
        return history[:max_examples]

    def _select_balanced(self, history: list[dict], max_examples: int) -> list[dict]:
        """Select balanced examples (recent + diverse types).

        Strategy:
        1. Take most recent 3 examples
        2. Ensure at least 1 REJECTED and 1 EDITED (if available)
        3. Avoid duplicates
        """
        # Group by result type
        rejected = [d for d in history if d.get("result") == "REJECT"]
        edited = [d for d in history if d.get("result") == "EDIT"]

        # Start with most recent
        examples = history[: min(3, max_examples)]

        # Ensure diversity
        has_rejected = any(d.get("result") == "REJECT" for d in examples)
        has_edited = any(d.get("result") == "EDIT" for d in examples)

        if not has_rejected and rejected and len(examples) < max_examples:
            examples.append(rejected[0])

        if not has_edited and edited and len(examples) < max_examples:
            examples.append(edited[0])

        # Remove duplicates while preserving order
        seen = set()
        unique_examples = []
        for ex in examples:
            key = (ex.get("turn_number"), ex.get("draft"))
            if key not in seen:
                seen.add(key)
                unique_examples.append(ex)

        return unique_examples[:max_examples]

    def _select_relevant(
        self, history: list[dict], instruction: str, max_examples: int
    ) -> list[dict]:
        """Select examples relevant to current instruction.

        Simple keyword matching for now.
        """
        # Extract keywords from instruction
        keywords = set(instruction.lower().split())

        # Score examples by keyword overlap
        scored = []
        for draft in history:
            draft_instruction = draft.get("instruction", "").lower()
            draft_keywords = set(draft_instruction.split())
            overlap = len(keywords & draft_keywords)
            scored.append((overlap, draft))

        # Sort by score (descending) and take top examples
        scored.sort(key=lambda x: x[0], reverse=True)
        return [draft for _, draft in scored[:max_examples]]

    def format_examples(
        self, examples: list[dict], format_style: str | None = None
    ) -> str:
        """Format examples for prompt injection.

        Args:
            examples: Selected examples
            format_style: Format style ("concise" or "detailed", uses config if None)

        Returns:
            Formatted string for prompt
        """
        if not examples:
            return ""

        format_style = format_style or self.config.format_style

        if format_style == "concise":
            return self._format_concise(examples)
        elif format_style == "detailed":
            return self._format_detailed(examples)
        else:
            return self._format_concise(examples)

    def _format_concise(self, examples: list[dict]) -> str:
        """Format examples in concise style (saves tokens)."""
        lines = ["## Learning from recent feedback", ""]

        for ex in examples:
            turn_num = ex.get("turn_number", "?")
            instruction = ex.get("instruction", "")
            draft = ex.get("draft", "")
            result = ex.get("result", "")
            edited = ex.get("edited")
            rejection_reason = ex.get("rejection_reason")

            # Format based on result type
            if result == "REJECT":
                line = f'[Turn {turn_num}] "{instruction}"\n❌ REJECTED: "{draft}"'
                if rejection_reason and self.config.enable_rejection_reason:
                    line += f"\n   Reason: {rejection_reason}"
            elif result == "EDIT" and edited:
                # Truncate for brevity
                draft_short = draft[:80] + "..." if len(draft) > 80 else draft
                edited_short = edited[:80] + "..." if len(edited) > 80 else edited
                line = f'[Turn {turn_num}] "{instruction}"\n✏️ EDITED: "{draft_short}" → "{edited_short}"'
            else:
                continue

            lines.append(line)
            lines.append("")  # Empty line between examples

        return "\n".join(lines)

    def _format_detailed(self, examples: list[dict]) -> str:
        """Format examples in detailed style (more verbose)."""
        lines = ["## Learning from recent feedback", ""]

        for i, ex in enumerate(examples, 1):
            turn_num = ex.get("turn_number", "?")
            instruction = ex.get("instruction", "")
            draft = ex.get("draft", "")
            result = ex.get("result", "")
            edited = ex.get("edited")
            rejection_reason = ex.get("rejection_reason")

            if result == "REJECT":
                lines.append(f"Example {i} (NEGATIVE):")
                lines.append(f"Instruction: {instruction}")
                lines.append(f'Your response: "{draft}"')
                feedback = f"Feedback: REJECTED"
                if rejection_reason:
                    feedback += f" - {rejection_reason}"
                lines.append(feedback)
            elif result == "EDIT" and edited:
                lines.append(f"Example {i} (IMPROVEMENT):")
                lines.append(f"Instruction: {instruction}")
                lines.append(f'Original: "{draft}"')
                lines.append(f'Edited to: "{edited}"')
                lines.append("Feedback: ACCEPTED after edit")
            else:
                continue

            lines.append("")  # Empty line between examples

        return "\n".join(lines)
