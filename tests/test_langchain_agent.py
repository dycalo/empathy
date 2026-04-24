"""Tests for LangChain agent implementation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from empathy.agents.langchain_agent import LangChainAgent
from empathy.core.models import Turn, TurnSource


class TestLangChainAgent:
    """Tests for LangChainAgent."""

    @pytest.fixture
    def dialogue_dir(self, tmp_path: Path) -> Path:
        """Create a temporary dialogue directory."""
        dialogue_dir = tmp_path / "test_dialogue"
        dialogue_dir.mkdir()
        return dialogue_dir

    @pytest.fixture
    def transcript_path(self, tmp_path: Path) -> Path:
        """Create a temporary transcript path."""
        return tmp_path / "transcript.jsonl"

    def test_agent_initialization(self, dialogue_dir: Path, transcript_path: Path):
        """Test that LangChainAgent initializes correctly."""
        agent = LangChainAgent(
            side="therapist",
            model="claude-haiku-4-5-20251001",
            dialogue_dir=dialogue_dir,
            transcript_path=transcript_path,
            api_key="test-key",
        )

        assert agent.side == "therapist"
        assert agent.model == "claude-haiku-4-5-20251001"
        assert agent.dialogue_dir == dialogue_dir
        assert agent.transcript_path == transcript_path
        assert agent.base_agent is not None
        assert agent._agent_graph is None  # Lazy initialization

    def test_process_result_terminal_speak(self, dialogue_dir: Path, transcript_path: Path):
        """Test processing result with terminal speak marker."""
        agent = LangChainAgent(
            side="therapist",
            dialogue_dir=dialogue_dir,
            transcript_path=transcript_path,
            api_key="test-key",
        )

        result = agent._process_result("__TERMINAL_SPEAK__:Hello, how are you feeling?")

        assert result.type == "draft"
        assert result.content == "Hello, how are you feeling?"

    def test_process_result_terminal_speak_with_whitespace(
        self, dialogue_dir: Path, transcript_path: Path
    ):
        """Test processing result with terminal speak marker and extra whitespace."""
        agent = LangChainAgent(
            side="client",
            dialogue_dir=dialogue_dir,
            transcript_path=transcript_path,
            api_key="test-key",
        )

        result = agent._process_result("__TERMINAL_SPEAK__:  I'm feeling anxious  ")

        assert result.type == "draft"
        assert result.content == "I'm feeling anxious"

    def test_process_result_clarification(self, dialogue_dir: Path, transcript_path: Path):
        """Test processing result without terminal speak marker."""
        agent = LangChainAgent(
            side="therapist",
            dialogue_dir=dialogue_dir,
            transcript_path=transcript_path,
            api_key="test-key",
        )

        result = agent._process_result("Could you clarify what you mean by that?")

        assert result.type == "clarification"
        assert result.content == "Could you clarify what you mean by that?"

    def test_process_result_empty_speak(self, dialogue_dir: Path, transcript_path: Path):
        """Test processing result with empty speak content."""
        agent = LangChainAgent(
            side="therapist",
            dialogue_dir=dialogue_dir,
            transcript_path=transcript_path,
            api_key="test-key",
        )

        result = agent._process_result("__TERMINAL_SPEAK__:")

        assert result.type == "draft"
        assert result.content == ""

    @patch("empathy.agents.langchain_agent.create_agent")
    def test_initialize_agent_executor_therapist(
        self, mock_create_agent, dialogue_dir: Path, transcript_path: Path
    ):
        """Test agent executor initialization for therapist."""
        mock_graph = MagicMock()
        mock_create_agent.return_value = mock_graph

        agent = LangChainAgent(
            side="therapist",
            dialogue_dir=dialogue_dir,
            transcript_path=transcript_path,
            api_key="test-key",
        )

        graph = agent._initialize_agent_executor()

        assert graph == mock_graph
        mock_create_agent.assert_called_once()
        call_kwargs = mock_create_agent.call_args[1]
        assert "therapist" in call_kwargs["system_prompt"].lower()
        assert "clinical records" in call_kwargs["system_prompt"].lower()

    @patch("empathy.agents.langchain_agent.create_agent")
    def test_initialize_agent_executor_client(
        self, mock_create_agent, dialogue_dir: Path, transcript_path: Path
    ):
        """Test agent executor initialization for client."""
        mock_graph = MagicMock()
        mock_create_agent.return_value = mock_graph

        agent = LangChainAgent(
            side="client",
            dialogue_dir=dialogue_dir,
            transcript_path=transcript_path,
            api_key="test-key",
        )

        graph = agent._initialize_agent_executor()

        assert graph == mock_graph
        mock_create_agent.assert_called_once()
        call_kwargs = mock_create_agent.call_args[1]
        assert "client" in call_kwargs["system_prompt"].lower()
        assert "emotions" in call_kwargs["system_prompt"].lower()

    @patch("empathy.agents.langchain_agent.create_agent")
    def test_initialize_agent_executor_with_system_context(
        self, mock_create_agent, dialogue_dir: Path, transcript_path: Path
    ):
        """Test agent executor initialization with additional system context."""
        mock_graph = MagicMock()
        mock_create_agent.return_value = mock_graph

        agent = LangChainAgent(
            side="therapist",
            dialogue_dir=dialogue_dir,
            transcript_path=transcript_path,
            api_key="test-key",
        )

        system_context = "Additional context: Focus on CBT techniques."
        graph = agent._initialize_agent_executor(system_context)

        assert graph == mock_graph
        call_kwargs = mock_create_agent.call_args[1]
        assert "CBT techniques" in call_kwargs["system_prompt"]

    def test_fallback_to_base_agent_on_error(
        self, dialogue_dir: Path, transcript_path: Path
    ):
        """Test that agent falls back to BaseAgent on error."""
        agent = LangChainAgent(
            side="therapist",
            dialogue_dir=dialogue_dir,
            transcript_path=transcript_path,
            api_key="test-key",
        )

        # Mock _call_agent_with_retry to raise an exception
        with patch.object(agent, "_call_agent_with_retry", side_effect=Exception("Test error")):
            # Mock base_agent.generate_draft to return a result
            mock_result = MagicMock()
            mock_result.type = "draft"
            mock_result.content = "Fallback response"
            agent.base_agent.generate_draft = MagicMock(return_value=mock_result)

            result = agent.generate_draft(
                instruction="Say hello",
                transcript=[],
            )

            assert result.type == "draft"
            assert result.content == "Fallback response"
            agent.base_agent.generate_draft.assert_called_once()

    def test_summarize_delegates_to_base_agent(
        self, dialogue_dir: Path, transcript_path: Path
    ):
        """Test that summarize delegates to BaseAgent."""
        agent = LangChainAgent(
            side="therapist",
            dialogue_dir=dialogue_dir,
            transcript_path=transcript_path,
            api_key="test-key",
        )

        turns = [
            Turn.create(
                speaker="therapist",
                source=TurnSource.AGENT_ACCEPT,
                content="Hello",
            )
        ]

        # Mock base_agent.summarize
        agent.base_agent.summarize = MagicMock(return_value="Summary text")

        result = agent.summarize(turns, "Previous summary")

        assert result == "Summary text"
        agent.base_agent.summarize.assert_called_once_with(turns, "Previous summary")
