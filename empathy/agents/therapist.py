"""Therapist-side agent."""

from __future__ import annotations

from typing import Any

from empathy.agents.base import BaseAgent


class TherapistAgent(BaseAgent):
    """LLM agent acting as the therapist."""

    def __init__(
        self,
        *,
        knowledge: str = "",
        dialogue_background: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            side="therapist",
            knowledge=knowledge,
            dialogue_background=dialogue_background,
            **kwargs,
        )

    def _role_preamble(self) -> str:
        return (
            "You are a professional therapist conducting a structured counseling session. "
            "A human controller is guiding your responses via brief instructions. "
            "Generate a single natural utterance as the therapist. "
            "Output ONLY the spoken text — no stage directions, role labels, or metadata."
        )
