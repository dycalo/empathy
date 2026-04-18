"""Base LLM agent using the Anthropic API with prompt caching."""

from __future__ import annotations

import os
from dataclasses import dataclass as _dataclass
from typing import Any, cast
from typing import Literal as _Literal

import anthropic
from anthropic.types import MessageParam, TextBlockParam

from empathy.agents.context import _MAX_FEEDBACK_DRAFTS as _MAX_FEEDBACK_DRAFTS  # re-export
from empathy.agents.context import ContextBuilder
from empathy.core.models import Draft, Speaker, Turn


@_dataclass
class GenerateResult:
    type: _Literal["draft", "clarification"]
    content: str


_DEFAULT_MODEL = os.environ.get("EMPATHY_MODEL")

# Maximum tool-call rounds per generate_draft call (prevents infinite loops).
_MAX_TOOL_ROUNDS = 5

_SUMMARY_PROMPT = """
You are summarizing an ongoing therapeutic dialogue between a therapist and a client.
Condense the following conversation turns into a concise summary (max 400 words).

Focus on:
1. Key emotional states and how they evolved
2. Therapeutic themes discussed (e.g. anxiety, relationship patterns, coping strategies)
3. Important disclosures or breakthroughs by the client
4. Therapeutic techniques used by the therapist (e.g. reflection, reframing, CBT exercises)
5. The current relational dynamic between therapist and client
6. Any unresolved topics or open threads

Do NOT include verbatim quotes. Summarize in third person.
If a previous summary exists, integrate the new turns into it rather than restarting.

{previous_summary_section}
## Turns to summarize

{turns_text}"""


class BaseAgent:
    """Generates dialogue draft turns for one side of a therapeutic conversation.

    The agent is stateless between calls; transcript and draft history are
    passed in on every ``generate_draft`` call so the caller controls what
    context is injected.
    """

    def __init__(
        self,
        side: Speaker,
        *,
        model: str = _DEFAULT_MODEL or "claude-haiku-4-5-20251001",
        knowledge: str = "",
        dialogue_background: str = "",
        api_key: str | None = None,
        max_tokens: int = 1024,
        mcp_provider: Any | None = None,
    ) -> None:
        self.side = side
        self.model = model
        self.max_tokens = max_tokens
        self._knowledge = knowledge
        self._dialogue_background = dialogue_background
        base_url = os.environ.get("EMPATHY_BASE_URL")
        resolved_api_key = api_key or os.environ.get("EMPATHY_API_KEY")
        self._client = anthropic.Anthropic(api_key=resolved_api_key, base_url=base_url)
        self._mcp_provider = mcp_provider

        mcp_tools = mcp_provider.tool_params() if mcp_provider and not mcp_provider.is_empty else []
        mcp_instructions = mcp_provider.instructions if mcp_provider else ""

        self._context_builder = ContextBuilder(
            side=self.side,
            role_preamble=self._role_preamble(),
            knowledge=knowledge,
            dialogue_background=dialogue_background,
            mcp_tools=mcp_tools,
            mcp_instructions=mcp_instructions,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_draft(
        self,
        instruction: str,
        transcript: list[Turn],
        draft_history: list[Draft] | None = None,
        *,
        active_skills: list[Any] | None = None,
        summary: str = "",
    ) -> GenerateResult:
        """Call the Anthropic API and return the raw draft text.

        When MCP tools are configured, automatically handles tool-use rounds
        (up to ``_MAX_TOOL_ROUNDS``) before returning the final text response.

        Args:
            instruction: Natural-language instruction from the controller.
            transcript: Windowed transcript turns to include in context.
            draft_history: Optional history of drafts for feedback signals.
            active_skills: Skills to inject into the dynamic system prompt zone.
            summary: Conversation summary for turns outside the active window.
        """
        # Store current skills for tool use before loop
        if isinstance(active_skills, dict):
            self._current_skills = active_skills
        else:
            self._current_skills = {s.name: s for s in (active_skills or [])}

        ctx = self._context_builder.build(
            instruction,
            transcript,
            draft_history or [],
            active_skills=active_skills,
            summary=summary,
        )

        base_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": cast(list[TextBlockParam], ctx.system),
        }
        if ctx.tools:
            base_kwargs["tools"] = ctx.tools

        messages: list[Any] = list(ctx.messages)

        for round_idx in range(_MAX_TOOL_ROUNDS + 1):
            response = self._client.messages.create(
                **base_kwargs,
                messages=cast(list[MessageParam], messages),
            )

            # speak is a terminal tool — no tool_result sent back
            speak_uses = [b for b in response.content if b.type == "tool_use" and b.name == "speak"]
            if speak_uses:
                raw = (speak_uses[0].input or {}).get("content", "")
                return GenerateResult(type="draft", content=str(raw).strip())

            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                # No tool call — plain text means agent is requesting clarification
                text_block = next((b for b in response.content if b.type == "text"), None)
                if text_block is None:
                    raise ValueError(
                        f"No text block in Anthropic response (round {round_idx}). "
                        f"Block types: {[b.type for b in response.content]}"
                    )
                return GenerateResult(type="clarification", content=text_block.text.strip())

            if round_idx == _MAX_TOOL_ROUNDS:
                raise ValueError(
                    f"Tool-use loop exceeded {_MAX_TOOL_ROUNDS} rounds without a text response."
                )

            # Append assistant's tool-use turn, then the tool results.
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {"type": b.type, "text": b.text}
                        if b.type == "text"
                        else {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                        for b in response.content
                    ],
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": b.id,
                            "content": self._invoke_tool(b.name, dict(b.input)),
                        }
                        for b in tool_uses
                    ],
                }
            )

        raise AssertionError("unreachable")  # loop always returns or raises above

    def summarize(self, turns: list[Turn], existing_summary: str = "") -> str:
        """Generate a compressed summary of overflow transcript turns.

        Called by ``DialogueSession`` when the transcript exceeds the active
        context window. Returns the existing summary unchanged if turns is empty.
        """
        if not turns:
            return existing_summary

        turns_text = "".join(f"[{t.speaker.upper()}]: {t.content}" for t in turns)
        previous_section = (
            f"## Previous summary (integrate, do not repeat){existing_summary}"
            if existing_summary
            else ""
        )
        prompt = _SUMMARY_PROMPT.format(
            previous_summary_section=previous_section,
            turns_text=turns_text,
        )
        response = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        block = response.content[0]
        if block.type != "text":
            return existing_summary
        return block.text.strip()

    # ------------------------------------------------------------------
    # Overridable by subclasses
    # ------------------------------------------------------------------

    def _role_preamble(self) -> str:
        """Opening paragraph describing the agent's role."""
        other = "client" if self.side == "therapist" else "therapist"
        return (
            f"You are the {self.side} in a structured therapeutic dialogue "
            f"with a {other}. A human controller directs you via brief instructions. "
            f"EVERY instruction is a dialogue directive — always generate a reply "
            f"by calling the speak tool. Never treat an instruction as a question "
            f"directed at you.\n\n"
            f"Examples of brief instructions and what to do:\n"
            f'- "hi" / "hello" → generate an appropriate greeting as the {self.side}\n'
            f'- "continue" / "go ahead" → produce the natural next utterance\n'
            f'- a single word or phrase (e.g. "anxiety", "deeper") → use it as a '
            f"thematic cue for your next line\n"
            f'- "ask about childhood" → follow the directive in your reply\n\n'
            f"Rules:\n"
            f"- ALWAYS call speak with your dialogue text — no stage directions, "
            f"role labels, or metadata.\n"
            f"- Maintain coherence with the conversation history in the messages.\n"
            f"- Only ask for clarification (plain text, no speak call) when the "
            f"instruction is truly ambiguous AND the conversation history provides "
            f"no context to resolve it. This should be rare."
        )

    def _invoke_tool(self, name: str, inputs: dict[str, Any]) -> str:
        """Invoke a tool by name and return the result as a string.

        Override this method to connect to an actual MCP server or local tool
        implementations. The default stub returns an informative error message
        that the agent can incorporate into its response.
        """
        if name in ("apply_behavior", "apply_therapy"):
            skill_name = inputs.get("skill_name")
            if hasattr(self, "_current_skills") and skill_name in self._current_skills:
                from empathy.extensions.skills import read_skill_body

                return read_skill_body(self._current_skills[skill_name])
            return "Error: Skill not found or not enabled."

        return (
            f"[Tool '{name}' is not connected. "
            "Configure an MCP server in .empathy/tools/ to enable tool use.]"
        )

    # ------------------------------------------------------------------
    # Internal helpers — delegate to ContextBuilder
    # ------------------------------------------------------------------

    def _build_system(self) -> list[dict[str, Any]]:
        return self._context_builder.build_system()

    def _build_messages(
        self,
        turns: list[Turn],
        draft_history: list[Draft],
        instruction: str,
    ) -> list[dict[str, Any]]:
        return self._context_builder.build_messages(turns, draft_history, instruction)

    def _format_feedback(self, draft_history: list[Draft]) -> str:
        return self._context_builder.format_feedback(draft_history)
