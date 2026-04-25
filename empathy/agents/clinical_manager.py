"""Clinical observation manager for automatic therapeutic assessment (therapist only)."""

from __future__ import annotations

import fcntl
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import anthropic

from empathy.core.models import Turn


class ClinicalObservationManager:
    """Manages therapist clinical observations with automatic generation."""

    def __init__(self, dialogue_dir: Path, model: str = "claude-haiku-4-5-20251001"):
        """Initialize clinical observation manager.

        Args:
            dialogue_dir: Path to dialogue directory
            model: Model to use for observation generation
        """
        self.dialogue_dir = dialogue_dir
        self.model = model
        self.obs_dir = dialogue_dir / ".empathy" / "therapist" / "observations"
        self.obs_dir.mkdir(parents=True, exist_ok=True)

        self.current_path = self.obs_dir / "current.json"
        self.history_path = self.obs_dir / "history.jsonl"

        # Initialize Anthropic client
        api_key = os.environ.get("EMPATHY_API_KEY")
        base_url = os.environ.get("EMPATHY_BASE_URL")
        self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)

    def load_current(self) -> dict | None:
        """Load current clinical observation.

        Returns:
            Current observation dict, or None if not exists
        """
        if not self.current_path.exists():
            return None

        try:
            return json.loads(self.current_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def auto_generate(
        self,
        client_turn: Turn,
        current_observation: dict | None,
        therapist_knowledge: str = "",
        active_skills: list | dict | None = None,
        client_emotion_state: dict | None = None,
    ) -> dict:
        """Automatically generate clinical observation based on client's response.

        Args:
            client_turn: Latest client turn
            current_observation: Current observation (or None for initial)
            therapist_knowledge: Therapist's guidelines and knowledge
            active_skills: Active therapeutic techniques/skills
            client_emotion_state: Client's current emotion state (if available)

        Returns:
            Updated observation dict
        """
        # Build prompt for observation generation
        system_prompt = self._build_observation_prompt(therapist_knowledge, active_skills)
        user_message = self._build_observation_input(
            client_turn, current_observation, client_emotion_state
        )

        # Call LLM for observation generation
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=800,
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

            new_observation = json.loads(content)

            # Add metadata
            new_observation["timestamp"] = datetime.now(UTC).isoformat()
            new_observation["turn_number"] = client_turn.turn_number

            return new_observation

        except (json.JSONDecodeError, anthropic.APIError, KeyError) as e:
            # Fallback: return current observation or default observation
            if current_observation:
                return current_observation

            # Default initial observation
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "turn_number": client_turn.turn_number,
                "client_presentation": "neutral",
                "emotional_shift": "stable",
                "therapeutic_alliance": "establishing",
                "intervention_effectiveness": "N/A",
                "clinical_focus": [],
                "risk_factors": [],
                "reasoning": f"Fallback due to error: {str(e)}",
            }

    def get_prompt_injection(self, observation: dict) -> str:
        """Generate prompt injection text for therapist agent.

        Args:
            observation: Clinical observation dict

        Returns:
            Formatted prompt text
        """
        presentation = observation.get("client_presentation", "neutral")
        shift = observation.get("emotional_shift", "stable")
        alliance = observation.get("therapeutic_alliance", "establishing")
        effectiveness = observation.get("intervention_effectiveness", "N/A")
        focus = observation.get("clinical_focus", [])
        risks = observation.get("risk_factors", [])

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

    def save(self, observation: dict) -> None:
        """Save observation to current.json and append to history.jsonl.

        Args:
            observation: Observation dict to save
        """
        # Write current observation
        self.current_path.write_text(json.dumps(observation, indent=2, ensure_ascii=False))

        # Append to history with exclusive lock
        with self.history_path.open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(json.dumps(observation, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _build_observation_prompt(self, therapist_knowledge: str = "", active_skills=None) -> str:
        """Build system prompt for observation generation.

        Args:
            therapist_knowledge: Therapist's guidelines
            active_skills: Active therapeutic techniques

        Returns:
            System prompt string
        """
        base_prompt = "You are a clinical supervisor analyzing a therapy session."

        # Add therapist guidelines if provided
        if therapist_knowledge:
            base_prompt += f"\n\n## Therapist guidelines\n\n{therapist_knowledge}"

        # Add active therapeutic techniques if provided
        if active_skills:
            skills_text = self._format_skills(active_skills)
            if skills_text:
                base_prompt += f"\n\n## Active therapeutic techniques\n\n{skills_text}"

        base_prompt += """

## Your task

Analyze the client's response and generate a clinical observation to guide the therapist's next intervention.

Consider these dimensions:
1. Client presentation: How is the client presenting emotionally and behaviorally?
2. Emotional shift: Has the client's emotional state changed? (improving/worsening/stable)
3. Therapeutic alliance: Quality of the therapeutic relationship (strong/establishing/strained)
4. Intervention effectiveness: How effective were the therapist's recent techniques?
5. Clinical focus: What areas need attention in the next intervention?
6. Risk factors: Any safety concerns or clinical risks to monitor?

Rules:
- Base your assessment on the client's actual response
- Consider the effectiveness of active therapeutic techniques
- Identify concrete focus areas for the next intervention
- Flag any risk factors (suicidal ideation, self-harm, crisis indicators)
- Keep observations concise and actionable

Output ONLY valid JSON in this exact format:
{
  "client_presentation": "anxious but engaged",
  "emotional_shift": "improving",
  "therapeutic_alliance": "establishing",
  "intervention_effectiveness": "active_listening helped client open up",
  "clinical_focus": ["explore work-related stress", "validate emotional experience"],
  "risk_factors": [],
  "reasoning": "Client responded positively to validation, showing increased openness"
}

Valid emotional_shift: improving, worsening, stable
Valid therapeutic_alliance: strong, establishing, strained"""

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

    def _build_observation_input(
        self,
        client_turn: Turn,
        current_observation: dict | None,
        client_emotion_state: dict | None,
    ) -> str:
        """Build user message for observation generation.

        Args:
            client_turn: Latest client turn
            current_observation: Current observation (or None)
            client_emotion_state: Client's emotion state (or None)

        Returns:
            Formatted user message
        """
        parts = []

        # Previous observation context
        if current_observation:
            obs_json = json.dumps(
                {
                    "client_presentation": current_observation.get("client_presentation", "neutral"),
                    "emotional_shift": current_observation.get("emotional_shift", "stable"),
                    "therapeutic_alliance": current_observation.get("therapeutic_alliance", "establishing"),
                    "intervention_effectiveness": current_observation.get("intervention_effectiveness", "N/A"),
                },
                indent=2,
                ensure_ascii=False,
            )
            parts.append(f"Previous observation:\n{obs_json}\n")
        else:
            parts.append("No previous observation (this is the first interaction).\n")

        # Client emotion state (if available)
        if client_emotion_state:
            emotion_summary = {
                "primary_emotion": client_emotion_state.get("primary_emotion", "neutral"),
                "intensity": client_emotion_state.get("intensity", 5),
                "change_direction": client_emotion_state.get("change_direction", "stable"),
            }
            parts.append(f"Client's emotion state:\n{json.dumps(emotion_summary, indent=2, ensure_ascii=False)}\n")

        # Client's response
        parts.append(f'Client just said: "{client_turn.content}"')
        parts.append("\nGenerate the updated clinical observation.")

        return "\n".join(parts)
