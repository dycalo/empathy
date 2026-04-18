"""Context assembly for Anthropic API calls.

``ContextBuilder`` is the single point where all prompt layers are combined
into a ``ContextResult`` ready to pass to ``anthropic.messages.create()``.

Layer layout::

    system prompt
      [static — ephemeral-cached]
        Block 1: role preamble
        Block 2: dialogue background  (if set)
        Block 3: knowledge / guidelines  (if set)
      [dynamic — not cached]
        Block 4: active skills  (injected per-turn)
        Block 5: MCP instructions  (Phase 3)

    messages
        conversation summary as first user message  (when present)
        windowed transcript turns
        feedback + controller instruction

    tools
        MCP tool definitions  (Phase 3, empty list for now)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from empathy.core.models import Draft, Speaker, Turn

_SPEAK_TOOL: dict[str, Any] = {
    "name": "speak",
    "description": (
        "Submit your dialogue turn. Call this tool when you have a genuine "
        "therapeutic response ready to deliver. The content will be shown to "
        "the controller for confirmation. "
        "IMPORTANT: Only use speak for actual spoken dialogue. If the controller's "
        "instruction is unclear, respond with a plain text clarification question "
        "instead — do NOT call speak."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Your exact dialogue utterance.",
            }
        },
        "required": ["content"],
    },
}

# How many recent rejected/edited drafts to include as feedback.
# Kept here (and re-exported from base) so existing tests can import it.
_MAX_FEEDBACK_DRAFTS = 5


@dataclass
class ContextResult:
    """Final assembled context, ready to pass to ``anthropic.messages.create()``."""

    system: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]


@dataclass
class WindowResult:
    """Output of ``ConversationWindow.select()``: which turns to include."""

    turns: list[Turn]  # turns to pass verbatim in the messages list
    summary: str  # existing summary text (empty if none)
    needs_new_summary: bool  # True → caller should generate an updated summary
    turns_to_summarize: list[Turn]  # turns that should be condensed


@dataclass
class ConversationWindow:
    """Partitions a transcript into a verbatim buffer and an overflow to summarise.

    Keeps the last ``buffer_turns`` turns verbatim; anything older is
    represented by a LLM-generated summary that the caller manages.
    """

    buffer_turns: int = 6  # number of most-recent turns to pass verbatim (~3 exchanges)

    def select(
        self,
        transcript: list[Turn],
        existing_summary: str = "",
        covers_turn_count: int = 0,
    ) -> WindowResult:
        """Decide which turns to include and whether a new summary is needed.

        Args:
            transcript: Full ordered list of committed turns.
            existing_summary: Previously generated summary text (empty if none).
            covers_turn_count: How many overflow turns the existing summary covers.
        """
        total = len(transcript)

        if total <= self.buffer_turns:
            # Everything fits in the buffer — no summary needed.
            return WindowResult(
                turns=transcript,
                summary=existing_summary,
                needs_new_summary=False,
                turns_to_summarize=[],
            )

        buffer = transcript[-self.buffer_turns :]
        overflow = transcript[: -self.buffer_turns]

        # Regenerate the summary when overflow has grown since the last snapshot.
        needs_new_summary = len(overflow) > covers_turn_count

        return WindowResult(
            turns=buffer,
            summary=existing_summary,
            needs_new_summary=needs_new_summary,
            turns_to_summarize=overflow,
        )


@dataclass
class ContextBuilder:
    """Assembles system prompt and messages for one side of a dialogue.

    Session-stable config (role, knowledge, background) is set at construction.
    Per-turn dynamic inputs (instruction, transcript, skills) are passed to
    :meth:`build` on every call.
    """

    side: Speaker
    role_preamble: str
    knowledge: str
    dialogue_background: str
    # ------------------------------------------------------------------ #
    # Phase 3 extension points — unused until MCP integration             #
    # ------------------------------------------------------------------ #
    mcp_tools: list[dict[str, Any]] = field(default_factory=list)
    mcp_instructions: str = ""

    def build(
        self,
        instruction: str,
        transcript: list[Turn],
        draft_history: list[Draft],
        *,
        active_skills: list[Any] | None = None,
        summary: str = "",
    ) -> ContextResult:
        """Assemble the full context for a single API call."""
        tools = [_SPEAK_TOOL] + list(self.mcp_tools)
        if active_skills:
            from empathy.extensions.skills import build_skill_tool

            # handle list or dict
            if isinstance(active_skills, dict):
                skills_dict = active_skills
            else:
                skills_dict = {s.name: s for s in active_skills}

            tools.append(build_skill_tool(self.side, skills_dict))

        return ContextResult(
            system=self.build_system(),
            messages=self.build_messages(transcript, draft_history, instruction, summary=summary),
            tools=tools,
        )

    def build_system(self) -> list[dict[str, Any]]:
        """Build the system prompt block list.

        Stable blocks (background, knowledge) are marked ephemeral so they can
        be cached by Anthropic across turns. Dynamic blocks (skills, MCP) come
        after the cache boundary and are never marked.
        """
        blocks: list[dict[str, Any]] = [
            {"type": "text", "text": self.role_preamble},
        ]

        if self.dialogue_background:
            blocks.append(
                {
                    "type": "text",
                    "text": f"## Scene background\n\n{self.dialogue_background}",
                    "cache_control": {"type": "ephemeral"},
                }
            )

        if self.knowledge:
            blocks.append(
                {
                    "type": "text",
                    "text": f"## Your guidelines\n\n{self.knowledge}",
                    "cache_control": {"type": "ephemeral"},
                }
            )

        if self.mcp_instructions:
            blocks.append(
                {
                    "type": "text",
                    "text": f"## Tool usage instructions\n\n{self.mcp_instructions}",
                }
            )

        return blocks

    def build_messages(
        self,
        turns: list[Turn],
        draft_history: list[Draft],
        instruction: str,
        *,
        summary: str = "",
    ) -> list[dict[str, Any]]:
        """Build the Anthropic messages list.

        - If ``summary`` is set it is injected as the first user message so the
          agent has context for turns that scrolled out of the active window.
        - Transcript turns → ``user``/``assistant`` based on speaker vs. side.
        - Consecutive same-role turns are merged (Anthropic requires alternating).
        - Feedback on recent rejected/edited drafts is prepended to the final
          controller instruction.
        - Ensures the first message is always a ``user`` message.
        """
        messages: list[dict[str, Any]] = []

        if summary:
            messages.append(
                {
                    "role": "user",
                    "content": f"## Conversation so far\n\n{summary}",
                }
            )

        for turn in turns:
            role = "assistant" if turn.speaker == self.side else "user"
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"] = f"{messages[-1]['content']}\n\n{turn.content}"
            else:
                messages.append({"role": role, "content": turn.content})

        # Anthropic requires the first message to be from "user"
        if messages and messages[0]["role"] == "assistant":
            messages.insert(0, {"role": "user", "content": "(dialogue begins)"})

        # Build the final user turn: optional feedback + controller instruction
        feedback = self.format_feedback(draft_history)
        final_user = (
            f"{feedback}\n\n---\n\nController instruction: {instruction}"
            if feedback
            else f"Controller instruction: {instruction}"
        )

        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] = f"{messages[-1]['content']}\n\n{final_user}"
        else:
            messages.append({"role": "user", "content": final_user})

        return messages

    def format_feedback(self, draft_history: list[Draft]) -> str:
        """Summarize recent REJECT/EDIT feedback for the agent.

        Only includes drafts authored by this side, most recent first.
        """
        recent = [
            d
            for d in draft_history[-(_MAX_FEEDBACK_DRAFTS * 2) :]
            if d.outcome in ("rejected", "edited") and d.speaker == self.side
        ][-_MAX_FEEDBACK_DRAFTS:]

        if not recent:
            return ""

        lines = ["## Feedback on your recent drafts (learn from these)"]
        for draft in recent:
            snippet = draft.content[:120]
            if draft.outcome == "rejected":
                lines.append(f'- REJECTED: "{snippet}"')
            else:
                original = draft.content[:80]
                final = (draft.final_content or "")[:80]
                lines.append(f'- EDITED: "{original}" → "{final}"')
        return "\n".join(lines)
