"""Speak tool - submit dialogue turn (terminal tool)."""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class SpeakInput(BaseModel):
    """Input schema for speak tool."""

    content: str = Field(description="Your exact dialogue utterance")


def create_speak_tool() -> StructuredTool:
    """Create the speak tool.

    This is a terminal tool - when called, it signals that the agent
    is ready to submit a dialogue turn. The content is NOT directly
    written to the transcript; instead, it's returned to the controller
    for human confirmation (accept/edit/reject).

    Returns:
        LangChain StructuredTool
    """

    def speak_func(content: str) -> str:
        """Submit your dialogue turn.

        This is a terminal action - after calling this, the agent
        will stop and wait for controller confirmation.
        """
        # Return special marker that LangChainAgent will detect
        return f"__TERMINAL_SPEAK__:{content}"

    return StructuredTool.from_function(
        func=speak_func,
        name="speak",
        description=(
            "Submit your dialogue turn. Call this tool when you have a genuine "
            "response ready to deliver. The content will be shown to the controller "
            "for confirmation. "
            "IMPORTANT: Only use speak for actual spoken dialogue. If the controller's "
            "instruction is unclear, respond with a plain text clarification question "
            "instead — do NOT call speak."
        ),
        args_schema=SpeakInput,
    )
