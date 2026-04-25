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

from empathy.agents.feedback import FeedbackConfig, FeedbackManager
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
    # ------------------------------------------------------------------ #
    # Feedback configuration                                              #
    # ------------------------------------------------------------------ #
    feedback_config: FeedbackConfig = field(default_factory=FeedbackConfig)

    def __post_init__(self):
        """Initialize FeedbackManager with config."""
        # FeedbackManager doesn't need dialogue_dir here since draft_history
        # is passed directly to format_feedback
        self._feedback_manager = FeedbackManager(
            dialogue_dir=None,
            config=self.feedback_config,
        )

    def build(
        self,
        instruction: str,
        transcript: list[Turn],
        draft_history: list[Draft],
        *,
        active_skills: list[Any] | None = None,
        summary: str = "",
        emotion_state: dict | None = None,
        clinical_observation: dict | None = None,
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
            system=self.build_system(emotion_state=emotion_state, clinical_observation=clinical_observation),
            messages=self.build_messages(transcript, draft_history, instruction, summary=summary),
            tools=tools,
        )

    def build_system(self, emotion_state: dict | None = None, clinical_observation: dict | None = None) -> list[dict[str, Any]]:
        """Build the system prompt block list.

        Stable blocks (background, knowledge) are marked ephemeral so they can
        be cached by Anthropic across turns. Dynamic blocks (skills, MCP, emotion, observation)
        come after the cache boundary and are never marked.
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

        # Add emotion state block (client only, dynamic)
        if emotion_state and self.side == "client":
            emotion_text = self._build_emotion_block(emotion_state)
            blocks.append(
                {
                    "type": "text",
                    "text": emotion_text,
                }
            )

        # Add clinical observation block (therapist only, dynamic)
        if clinical_observation and self.side == "therapist":
            observation_text = self._build_observation_block(clinical_observation)
            blocks.append(
                {
                    "type": "text",
                    "text": observation_text,
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

    def _build_emotion_block(self, emotion_state: dict) -> str:
        """Build emotion state block for client agent prompt.

        Args:
            emotion_state: Current emotion state dict

        Returns:
            Formatted emotion state text
        """
        primary = emotion_state.get("primary_emotion", "neutral")
        intensity = emotion_state.get("intensity", 5)
        physical = emotion_state.get("physical_sensations", [])
        thoughts = emotion_state.get("thoughts", "")
        change = emotion_state.get("change_direction", "stable")

        physical_text = ", ".join(physical) if physical else "none"
        thoughts_text = f'"{thoughts}"' if thoughts else "N/A"

        return f"""## Your current emotional state

Primary emotion: {primary} ({intensity}/10)
Physical sensations: {physical_text}
Current thoughts: {thoughts_text}
Recent change: {change}

When responding, embody this emotional state:
- Reflect the intensity in your language and tone
- Show physical sensations if relevant to the conversation
- Let your thoughts influence what you choose to share
- Adjust your openness based on your emotional state
"""

    def _build_observation_block(self, clinical_observation: dict) -> str:
        """Build clinical observation block for therapist agent prompt.

        Args:
            clinical_observation: Current clinical observation dict

        Returns:
            Formatted clinical observation text
        """
        presentation = clinical_observation.get("client_presentation", "neutral")
        shift = clinical_observation.get("emotional_shift", "stable")
        alliance = clinical_observation.get("therapeutic_alliance", "establishing")
        effectiveness = clinical_observation.get("intervention_effectiveness", "N/A")
        focus = clinical_observation.get("clinical_focus", [])
        risks = clinical_observation.get("risk_factors", [])

        focus_text = "\n".join(f"- {item}" for item in focus) if focus else "- None noted"
        risk_text = "\n".join(f"- {item}" for item in risks) if risks else "- None identified"

        return f"""## Clinical observation (therapist only)

Client presentation: {presentation}
Emotional shift: {shift}
Therapeutic alliance: {alliance}
Intervention effectiveness: {effectiveness}

Clinical focus areas:
{focus_text}

Risk factors:
{risk_text}

Use this observation to guide your therapeutic approach:
- Adjust your intervention based on effectiveness feedback
- Address clinical focus areas when appropriate
- Monitor and respond to risk factors
- Maintain awareness of alliance quality
"""

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
        feedback = self.format_feedback(draft_history, instruction)
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

    def format_feedback(self, draft_history: list[Draft], instruction: str = "") -> str:
        """Summarize recent REJECT/EDIT feedback for the agent using FeedbackManager.

        Only includes drafts authored by this side, most recent first.
        Uses intelligent sampling and formatting via FeedbackManager.
        """
        # Filter to this side's rejected/edited drafts
        relevant_history = [
            {
                "turn_number": i,
                "side": d.speaker,
                "instruction": d.source_instruction,
                "draft": d.content,
                "result": "REJECT" if d.outcome == "rejected" else "EDIT",
                "edited": d.final_content,
                "rejection_reason": getattr(d, "rejection_reason", None),
            }
            for i, d in enumerate(draft_history)
            if d.outcome in ("rejected", "edited") and d.speaker == self.side
        ]

        if not relevant_history:
            return ""

        # Use FeedbackManager for intelligent selection and formatting
        examples = self._feedback_manager.select_examples(
            relevant_history,
            instruction,
            max_examples=self.feedback_config.max_examples,
        )

        return self._feedback_manager.format_examples(
            examples,
            format_style=self.feedback_config.format_style,
        )
