"""Emotion state manager for automatic state transitions (client only)."""

from __future__ import annotations

import fcntl
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import anthropic

from empathy.core.models import Turn


class EmotionStateManager:
    """Manages client emotion state lifecycle with automatic transitions."""

    def __init__(self, dialogue_dir: Path, model: str = "claude-haiku-4-5-20251001"):
        """Initialize emotion state manager.

        Args:
            dialogue_dir: Path to dialogue directory
            model: Model to use for state transitions
        """
        self.dialogue_dir = dialogue_dir
        self.model = model
        self.state_dir = dialogue_dir / ".empathy" / "client" / "emotion-states"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.current_path = self.state_dir / "current.json"
        self.history_path = self.state_dir / "history.jsonl"

        # Initialize Anthropic client
        api_key = os.environ.get("EMPATHY_API_KEY")
        base_url = os.environ.get("EMPATHY_BASE_URL")
        self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)

    def load_current(self) -> dict | None:
        """Load current emotion state.

        Returns:
            Current emotion state dict, or None if not exists
        """
        if not self.current_path.exists():
            return None

        try:
            return json.loads(self.current_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def auto_update(
        self,
        therapist_turn: Turn,
        current_state: dict | None,
        client_knowledge: str = "",
        active_skills: list | dict | None = None,
    ) -> dict:
        """Automatically update emotion state based on therapist's statement.

        Args:
            therapist_turn: Latest therapist turn
            current_state: Current emotion state (or None for initial state)
            client_knowledge: Client's profile, personality, background
            active_skills: Active behavioral patterns/skills

        Returns:
            Updated emotion state dict
        """
        # Build prompt for state transition
        system_prompt = self._build_transition_prompt(client_knowledge, active_skills)
        user_message = self._build_transition_input(therapist_turn, current_state)

        # Call LLM for state transition
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            # Parse JSON response
            content = response.content[0].text.strip()
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            new_state = json.loads(content)

            # Add metadata
            new_state["timestamp"] = datetime.now(UTC).isoformat()
            new_state["turn_number"] = therapist_turn.turn_number + 1

            return new_state

        except (json.JSONDecodeError, anthropic.APIError, KeyError) as e:
            # Fallback: return current state or default state
            if current_state:
                return current_state

            # Default initial state
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "turn_number": therapist_turn.turn_number + 1,
                "primary_emotion": "neutral",
                "intensity": 5,
                "secondary_emotions": [],
                "triggers": [],
                "physical_sensations": [],
                "thoughts": "",
                "change_direction": "stable",
                "reasoning": f"Fallback due to error: {str(e)}",
            }

    def get_prompt_injection(self, state: dict) -> str:
        """Generate prompt injection text for client agent.

        Args:
            state: Emotion state dict

        Returns:
            Formatted prompt text
        """
        primary = state.get("primary_emotion", "neutral")
        intensity = state.get("intensity", 5)
        physical = state.get("physical_sensations", [])
        thoughts = state.get("thoughts", "")
        change = state.get("change_direction", "stable")

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

    def save(self, state: dict) -> None:
        """Save emotion state to current.json and append to history.jsonl.

        Args:
            state: Emotion state dict to save
        """
        # Write current state
        self.current_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))

        # Append to history with exclusive lock
        with self.history_path.open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(json.dumps(state, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _build_transition_prompt(self, client_knowledge: str = "", active_skills=None) -> str:
        """Build system prompt for state transition.

        Args:
            client_knowledge: Client's profile and personality
            active_skills: Active behavioral patterns

        Returns:
            System prompt string
        """
        base_prompt = "You are an emotion dynamics analyzer for a therapy client."

        # Add client profile if provided
        if client_knowledge:
            base_prompt += f"\n\n## Client profile\n\n{client_knowledge}"

        # Add active behavioral patterns if provided
        if active_skills:
            skills_text = self._format_skills(active_skills)
            if skills_text:
                base_prompt += f"\n\n## Active behavioral patterns\n\n{skills_text}"

        base_prompt += """

## Your task

Analyze how the therapist's statement affects THIS CLIENT's emotional state, considering their specific personality, background, and behavioral patterns.

Consider these dimensions:
1. Validation level (0-1): Does therapist acknowledge client's feelings?
2. Challenge level (0-1): Does therapist question client's thoughts?
3. Exploration depth (0-1): Does therapist invite deeper sharing?
4. Emotional tone (0-1): Warmth of therapist's response?

Based on this analysis and the client's profile, predict the updated emotion state.

Rules:
- Intensity changes should be gradual (max ±2 per turn)
- Consider how THIS CLIENT's personality affects their reaction
- High validation typically reduces anxiety/defensiveness (but depends on client)
- High challenge may increase anxiety or trigger defensiveness (especially for defensive clients)
- Warm tone generally promotes openness (but some clients may be suspicious)
- Consider the client's current state and behavioral patterns

Output ONLY valid JSON in this exact format:
{
  "primary_emotion": "anxious",
  "intensity": 6,
  "secondary_emotions": ["sad"],
  "triggers": ["work pressure", "fear of judgment"],
  "physical_sensations": ["chest tightness", "rapid heartbeat"],
  "thoughts": "Maybe I can talk about this",
  "change_direction": "decreasing",
  "reasoning": "Therapist's validation reduced anxiety slightly, consistent with client's need for acceptance"
}

Valid emotions: anxious, sad, angry, happy, fearful, ashamed, guilty, hopeful, neutral
Valid change_direction: increasing, decreasing, stable"""

        return base_prompt

    def _format_skills(self, active_skills) -> str:
        """Format active skills for prompt injection.

        Args:
            active_skills: List or dict of skills

        Returns:
            Formatted skills text
        """
        if not active_skills:
            return ""

        # Convert to list if dict
        if isinstance(active_skills, dict):
            skills_list = list(active_skills.values())
        else:
            skills_list = active_skills

        lines = []
        for skill in skills_list:
            # Handle both Skill objects and dicts
            if hasattr(skill, "name") and hasattr(skill, "description"):
                lines.append(f"- **{skill.name}**: {skill.description}")
            elif isinstance(skill, dict):
                name = skill.get("name", "Unknown")
                desc = skill.get("description", "")
                if desc:
                    lines.append(f"- **{name}**: {desc}")

        return "\n".join(lines)

    def _build_transition_input(self, therapist_turn: Turn, current_state: dict | None) -> str:
        """Build user message for state transition.

        Args:
            therapist_turn: Latest therapist turn
            current_state: Current emotion state (or None)

        Returns:
            Formatted user message
        """
        if current_state:
            state_json = json.dumps(
                {
                    "primary_emotion": current_state.get("primary_emotion", "neutral"),
                    "intensity": current_state.get("intensity", 5),
                    "triggers": current_state.get("triggers", []),
                    "thoughts": current_state.get("thoughts", ""),
                },
                indent=2,
                ensure_ascii=False,
            )
            state_text = f"Current emotion state:\n{state_json}\n\n"
        else:
            state_text = "No previous emotion state (this is the first interaction).\n\n"

        return f"""{state_text}Therapist just said: "{therapist_turn.content}"

Analyze the emotional impact and predict the updated emotion state."""
