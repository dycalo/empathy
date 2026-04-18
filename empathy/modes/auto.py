"""Auto mode: run N turns without human confirmation.

Both agents alternate turns. All turns are stored as TurnSource.AGENT_AUTO.
Draft-history is still written so the full record is preserved.
"""

from __future__ import annotations

from pathlib import Path

from empathy.agents.base import BaseAgent
from empathy.core.models import Draft, Speaker, Turn, TurnSource
from empathy.storage.drafts import append_draft, update_draft_outcome
from empathy.storage.transcript import append_turn, read_turns

_SIDES: list[Speaker] = ["therapist", "client"]


def run_auto(
    therapist: BaseAgent,
    client: BaseAgent,
    transcript_path: Path,
    drafts_path: Path,
    *,
    turns: int = 10,
    therapist_instruction: str = "Continue the dialogue naturally.",
    client_instruction: str = "Respond authentically.",
) -> list[Turn]:
    """Alternate therapist/client for *turns* total without human confirmation.

    Returns the list of committed turns (all sourced as AGENT_AUTO).
    Draft-history is also written for every turn.
    """
    committed: list[Turn] = []

    current_transcript = read_turns(transcript_path)
    if not current_transcript and turns > 0:
        draft = Draft.create(
            speaker="therapist",
            content="Hello, what brings you here today?",
            source_instruction="Initial greeting"
        )
        append_draft(drafts_path, draft)
        greeting = Turn.create(
            speaker="therapist",
            source=TurnSource.AGENT_AUTO,
            content="Hello, what brings you here today?",
            draft_id=draft.id
        )
        append_turn(transcript_path, greeting)
        update_draft_outcome(drafts_path, draft.id, "accepted")
        committed.append(greeting)
        turns -= 1

        # Start alternating from client side since therapist just greeted
        client_turn = True
    else:
        # Transcript isn't empty, continue normally from therapist
        client_turn = False

    for _i in range(turns):
        speaker: Speaker = "client" if client_turn else "therapist"
        client_turn = not client_turn

        agent = therapist if speaker == "therapist" else client
        instruction = therapist_instruction if speaker == "therapist" else client_instruction

        current_transcript = read_turns(transcript_path)
        result = agent.generate_draft(instruction, current_transcript)

        # If the agent asked a clarification question in auto mode, treat it as the turn content
        content = result.content

        draft = Draft.create(speaker=speaker, content=content, source_instruction=instruction)
        append_draft(drafts_path, draft)

        turn = Turn.create(
            speaker=speaker,
            source=TurnSource.AGENT_AUTO,
            content=content,
            draft_id=draft.id,
        )
        append_turn(transcript_path, turn)
        update_draft_outcome(drafts_path, draft.id, "accepted")
        committed.append(turn)

    return committed
