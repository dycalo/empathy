"""Client-side agent."""

from __future__ import annotations

from typing import Any

from empathy.agents.base import BaseAgent


class ClientAgent(BaseAgent):
    """LLM agent acting as the client/patient."""

    def __init__(
        self,
        *,
        knowledge: str = "",
        dialogue_background: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            side="client",
            knowledge=knowledge,
            dialogue_background=dialogue_background,
            **kwargs,
        )

    def _role_preamble(self) -> str:
        return (
            "You are a client attending a therapeutic counseling session. "
            "A human controller is guiding your responses via brief instructions. "
            "Generate a single natural utterance as the client. "
            "Output ONLY the spoken text — no stage directions, role labels, or metadata."
        )
