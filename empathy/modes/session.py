"""DialogueSession: orchestrates one side of a dialogue turn lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from empathy.agents.base import BaseAgent
from empathy.agents.context import ConversationWindow
from empathy.core.models import ClarificationMessage, Draft, Speaker, Turn, TurnSource
from empathy.extensions.skills import Skill
from empathy.storage.drafts import append_draft, read_drafts, update_draft_outcome
from empathy.storage.state import acquire_floor as _acquire
from empathy.storage.state import read_state
from empathy.storage.state import release_floor as _release
from empathy.storage.summary import read_summary, write_summary
from empathy.storage.transcript import append_turn, read_turns

_window = ConversationWindow()  # shared default window (buffer_turns=6)


@dataclass
class DialogueSession:
    """Manages storage and agent interactions for one side of a dialogue.

    This class is the single orchestration point for the turn lifecycle:
    generate draft → confirm (accept/edit/reject) → commit to transcript.
    """

    dialogue_dir: Path
    side: Speaker
    agent: BaseAgent

    # ------------------------------------------------------------------
    # Derived paths
    # ------------------------------------------------------------------

    @property
    def transcript_path(self) -> Path:
        return self.dialogue_dir / "transcript.jsonl"

    @property
    def drafts_path(self) -> Path:
        return self.dialogue_dir / "draft-history.jsonl"

    @property
    def state_path(self) -> Path:
        return self.dialogue_dir / ".empathy" / "state.json"

    @property
    def summary_path(self) -> Path:
        return self.dialogue_dir / ".empathy" / self.side / "summary.json"

    # ------------------------------------------------------------------
    # Floor management
    # ------------------------------------------------------------------

    def try_acquire_floor(self) -> bool:
        """Attempt to acquire the floor. Returns True on success."""
        return _acquire(self.state_path, self.side)

    def release_floor(self) -> None:
        """Release the floor if currently held by this side."""
        _release(self.state_path, self.side)

    def floor_status(self) -> dict[str, Any]:
        """Return current floor state (turn_number, floor_holder, etc.)."""
        return read_state(self.state_path)

    # ------------------------------------------------------------------
    # Storage reads
    # ------------------------------------------------------------------

    def get_transcript(self) -> list[Turn]:
        return read_turns(self.transcript_path)

    def get_draft_history(self) -> list[Draft]:
        return read_drafts(self.drafts_path)

    # ------------------------------------------------------------------
    # Turn lifecycle
    # ------------------------------------------------------------------

    def generate_draft(
        self,
        instruction: str,
        active_skills: list[Skill] | None = None,
    ) -> Draft | ClarificationMessage:
        """Call the agent with the current context and persist the draft.

        Applies context windowing: keeps the last ``buffer_turns`` turns
        verbatim and compresses older turns into a LLM-generated summary.
        Active skills are injected into the system prompt dynamic zone.

        The draft starts with outcome='pending'. The caller must subsequently
        call one of accept_draft / edit_draft / reject_draft to finalise it.
        """
        transcript = self.get_transcript()
        draft_history = self.get_draft_history()

        # Context window management
        existing_summary, covers_turn_count = read_summary(self.summary_path)
        window_result = _window.select(transcript, existing_summary, covers_turn_count)

        if window_result.needs_new_summary:
            new_summary = self.agent.summarize(window_result.turns_to_summarize, existing_summary)
            write_summary(self.summary_path, new_summary, len(window_result.turns_to_summarize))
            summary = new_summary
        else:
            summary = window_result.summary

        # Automatic emotion state transition (client only)
        emotion_state = None
        emotion_change = None  # Track emotion change for UI display
        if self.side == "client":
            from empathy.agents.emotion_manager import EmotionStateManager

            emotion_manager = EmotionStateManager(self.dialogue_dir, self.agent.model)
            current_state = emotion_manager.load_current()

            # Get therapist's latest turn
            therapist_turns = [t for t in transcript if t.speaker == "therapist"]
            if therapist_turns:
                last_therapist_turn = therapist_turns[-1]

                # Get client knowledge and skills for personalized state transition
                client_knowledge = self.agent.context_builder.knowledge

                emotion_state = emotion_manager.auto_update(
                    last_therapist_turn,
                    current_state,
                    client_knowledge=client_knowledge,
                    active_skills=active_skills,
                )
                emotion_manager.save(emotion_state)

                # Track emotion change for UI display
                if current_state:
                    emotion_change = {
                        "from_emotion": current_state.get("primary_emotion", "neutral"),
                        "from_intensity": current_state.get("intensity", 5),
                        "to_emotion": emotion_state.get("primary_emotion", "neutral"),
                        "to_intensity": emotion_state.get("intensity", 5),
                        "change_direction": emotion_state.get("change_direction", "stable"),
                        "reasoning": emotion_state.get("reasoning", ""),
                    }
                else:
                    # Initial state
                    emotion_change = {
                        "from_emotion": None,
                        "from_intensity": None,
                        "to_emotion": emotion_state.get("primary_emotion", "neutral"),
                        "to_intensity": emotion_state.get("intensity", 5),
                        "change_direction": "initial",
                        "reasoning": "Initial emotion state",
                    }

        # Automatic clinical observation (therapist only)
        clinical_observation = None
        observation_change = None  # Track observation change for UI display
        if self.side == "therapist":
            import os

            # Check if clinical observation is enabled
            if os.getenv("EMPATHY_CLINICAL_OBSERVATION", "1") == "1":
                from empathy.agents.clinical_manager import ClinicalObservationManager

                clinical_manager = ClinicalObservationManager(self.dialogue_dir, self.agent.model)
                current_observation = clinical_manager.load_current()

                # Get client's latest turn
                client_turns = [t for t in transcript if t.speaker == "client"]
                if client_turns:
                    last_client_turn = client_turns[-1]

                    # Get therapist knowledge and skills for observation
                    therapist_knowledge = self.agent.context_builder.knowledge

                    # Get client emotion state if available
                    client_emotion_state = None
                    emotion_state_path = self.dialogue_dir / ".empathy" / "client" / "emotion-states" / "current.json"
                    if emotion_state_path.exists():
                        import json
                        try:
                            client_emotion_state = json.loads(emotion_state_path.read_text())
                        except (json.JSONDecodeError, OSError):
                            pass

                    clinical_observation = clinical_manager.auto_generate(
                        last_client_turn,
                        current_observation,
                        therapist_knowledge=therapist_knowledge,
                        active_skills=active_skills,
                        client_emotion_state=client_emotion_state,
                    )
                    clinical_manager.save(clinical_observation)

                    # Track observation change for UI display
                    if current_observation:
                        observation_change = {
                            "from_presentation": current_observation.get("client_presentation", "neutral"),
                            "from_alliance": current_observation.get("therapeutic_alliance", "establishing"),
                            "to_presentation": clinical_observation.get("client_presentation", "neutral"),
                            "to_alliance": clinical_observation.get("therapeutic_alliance", "establishing"),
                            "emotional_shift": clinical_observation.get("emotional_shift", "stable"),
                            "reasoning": clinical_observation.get("reasoning", ""),
                        }
                    else:
                        # Initial observation
                        observation_change = {
                            "from_presentation": None,
                            "from_alliance": None,
                            "to_presentation": clinical_observation.get("client_presentation", "neutral"),
                            "to_alliance": clinical_observation.get("therapeutic_alliance", "establishing"),
                            "emotional_shift": "initial",
                            "reasoning": "Initial clinical observation",
                        }

        result = self.agent.generate_draft(
            instruction,
            window_result.turns,
            draft_history,
            active_skills=active_skills,
            summary=summary,
            emotion_state=emotion_state,
            clinical_observation=clinical_observation,
        )
        if result.type == "clarification":
            return ClarificationMessage(content=result.content)

        # Calculate conversation window range
        conversation_window = None
        if window_result.turns:
            # Find turn numbers in the windowed transcript
            turn_numbers = [i for i, t in enumerate(transcript) if t in window_result.turns]
            if turn_numbers:
                conversation_window = {
                    "start_turn": turn_numbers[0],
                    "end_turn": turn_numbers[-1],
                }

        # Extract API usage
        api_usage = None
        if result.usage:
            api_usage = {
                "input_tokens": result.usage.get("input_tokens", 0),
                "output_tokens": result.usage.get("output_tokens", 0),
                "cached_tokens": result.usage.get("cache_read_input_tokens", 0),
                "latency_ms": result.latency_ms or 0,
            }

        # Store API usage in hook_annotations for UI display
        hook_annotations = {"api_usage": api_usage} if api_usage else {}

        # Add emotion change info for UI display (client only)
        if emotion_change:
            hook_annotations["emotion_change"] = emotion_change

        # Add observation change info for UI display (therapist only)
        if observation_change:
            hook_annotations["observation_change"] = observation_change

        draft = Draft.create(
            self.side,
            result.content,
            instruction,
            conversation_window=conversation_window,
            api_usage=api_usage,
            model=self.agent.model,
            hook_annotations=hook_annotations,
        )
        append_draft(self.drafts_path, draft)
        return draft

    def accept_draft(self, draft: Draft) -> Turn:
        """Commit an agent draft verbatim (TurnSource.AGENT_ACCEPT)."""
        turn = Turn.create(
            speaker=self.side,
            source=TurnSource.AGENT_ACCEPT,
            content=draft.content,
            draft_id=draft.id,
        )
        append_turn(self.transcript_path, turn)
        update_draft_outcome(self.drafts_path, draft.id, "accepted")
        return turn

    def edit_draft(self, draft: Draft, edited_content: str) -> Turn:
        """Commit a controller-edited version of a draft (TurnSource.AGENT_EDIT).

        Both the final content and the original draft are stored so the diff
        is available as a training signal.
        """
        turn = Turn.create(
            speaker=self.side,
            source=TurnSource.AGENT_EDIT,
            content=edited_content,
            draft_id=draft.id,
            original_draft=draft.content,
        )
        append_turn(self.transcript_path, turn)
        update_draft_outcome(self.drafts_path, draft.id, "edited", final_content=edited_content)
        return turn

    def reject_draft(self, draft: Draft) -> None:
        """Discard a draft — it stays in draft-history but never enters transcript."""
        update_draft_outcome(self.drafts_path, draft.id, "rejected")

    def commit_human_turn(self, content: str) -> Turn:
        """Bypass the agent — commit a turn typed directly by the controller."""
        turn = Turn.create(
            speaker=self.side,
            source=TurnSource.HUMAN,
            content=content,
        )
        append_turn(self.transcript_path, turn)
        return turn
