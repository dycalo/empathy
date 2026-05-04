"""LangChain-based agent implementation for Empathy.

This module provides the primary agent implementation using LangChain's
agent framework with enhanced tool management, error handling, and retry mechanisms.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Literal

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from empathy.agents.context import ContextBuilder
from empathy.core.models import Draft, Speaker, Turn

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.environ.get("EMPATHY_MODEL", "claude-haiku-4-5-20251001")


@dataclass
class GenerateResult:
    """Result from agent generation."""

    type: Literal["draft", "clarification"]
    content: str
    usage: dict[str, int] | None = None
    latency_ms: int | None = None


class LangChainAgent:
    """LangChain-powered agent for dialogue generation.

    This agent uses LangChain's AgentExecutor to manage tool calls,
    with automatic retry and error handling.
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
        dialogue_dir: Any = None,
        transcript_path: Any = None,
        user_id: str | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize LangChain agent.

        Args:
            side: Speaker side ("therapist" or "client")
            model: Model name
            knowledge: Knowledge/guidelines text
            dialogue_background: Dialogue background text
            api_key: Anthropic API key
            max_tokens: Max tokens for generation
            mcp_provider: Optional MCP provider
            dialogue_dir: Path to dialogue directory
            transcript_path: Path to transcript.jsonl
            user_id: User identifier for user-level tools (e.g. memory)
            verbose: Enable verbose logging
        """
        self.side = side
        self.model = model
        self.max_tokens = max_tokens
        self.verbose = verbose
        self.dialogue_dir = dialogue_dir
        self.transcript_path = transcript_path
        self.user_id = user_id
        self._mcp_provider = mcp_provider

        # Initialize LangChain LLM
        resolved_api_key = api_key or os.environ.get("EMPATHY_API_KEY")
        base_url = os.environ.get("EMPATHY_BASE_URL")

        self.llm = ChatAnthropic(
            model=model,
            anthropic_api_key=resolved_api_key,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        # Initialize context builder
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

        # Agent executor (initialized lazily)
        self._agent_graph: Any | None = None

    @property
    def context_builder(self) -> ContextBuilder:
        """Get context builder for external access."""
        return self._context_builder

    def _initialize_agent_executor(self, system_context: str = "") -> Any:
        """Initialize LangChain agent graph.

        Args:
            system_context: Additional system context from ContextBuilder

        Returns:
            Configured agent graph
        """
        from empathy.agents.tools import create_all_tools

        # Create tools
        tools = create_all_tools(
            side=self.side,
            user_id=self.user_id,
            dialogue_dir=self.dialogue_dir,
            transcript_path=self.transcript_path,
            mcp_provider=self._mcp_provider,
        )

        # Create enhanced system prompt based on side
        if self.side == "therapist":
            base_prompt = (
                "You are a professional therapist conducting a counseling session.\n\n"
                "## Available Tools\n"
                "You have access to several tools to help you:\n"
                "- **speak**: Submit your dialogue turn when ready to respond\n"
                "- **record**: Manage clinical records (assessment/progress_note/treatment_plan/observation)\n"
                "- **memory_manage**: Store and retrieve important patterns, insights, and key events\n\n"
                "## Workflow\n"
                "1. Use 'record' to document clinical observations\n"
                "2. Use 'memory_manage' to store important insights\n"
                "3. Use 'speak' when ready to respond to the client\n\n"
                "## Important\n"
                "- ALWAYS call 'speak' with your dialogue text when ready to respond\n"
                "- Use tools proactively to maintain clinical records and track patterns\n"
                "- Only ask for clarification (plain text, no speak call) when truly ambiguous\n\n"
            )
        else:  # client
            base_prompt = (
                "You are a client in a counseling session.\n\n"
                "## Available Tools\n"
                "You have access to several tools:\n"
                "- **speak**: Submit your dialogue turn when ready to respond\n"
                "- **emotion_state**: Track your emotional state (primary_emotion/intensity/triggers)\n"
                "- **memory_manage**: Store important memories and insights\n\n"
                "## Workflow\n"
                "1. Use 'emotion_state' to update how you're feeling\n"
                "2. Use 'memory_manage' to note important realizations\n"
                "3. Use 'speak' when ready to respond\n\n"
                "## Important\n"
                "- ALWAYS call 'speak' with your dialogue text when ready to respond\n"
                "- Express your emotions naturally through the tools and dialogue\n"
                "- Only ask for clarification when truly confused\n\n"
            )

        # Append system context if provided
        system_prompt = base_prompt + system_context if system_context else base_prompt

        # Create agent using new API
        agent_graph = create_agent(
            model=self.llm,
            tools=tools,
            system_prompt=system_prompt,
            debug=self.verbose,
        )

        return agent_graph

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_agent_with_retry(self, instruction: str, system_context: str = "") -> str:
        """Call agent with automatic retry on transient failures.

        Args:
            instruction: Controller instruction
            system_context: Additional system context from ContextBuilder

        Returns:
            Agent output

        Raises:
            Exception: If all retries fail
        """
        if self._agent_graph is None:
            self._agent_graph = self._initialize_agent_executor(system_context)

        try:
            # Invoke agent graph with new API
            result = self._agent_graph.invoke({"messages": [("user", instruction)]})

            # Debug logging
            if self.verbose:
                logger.debug(f"Agent result type: {type(result)}")
                logger.debug(f"Agent result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")

            # Extract the final message
            messages = result.get("messages", [])
            if self.verbose:
                logger.debug(f"Messages count: {len(messages)}")
                if messages:
                    logger.debug(f"Last message type: {type(messages[-1])}")

            if messages:
                last_message = messages[-1]
                # Handle different message types
                if hasattr(last_message, "content"):
                    content = last_message.content
                    if self.verbose:
                        logger.debug(f"Message content type: {type(content)}")
                    # If content is a list (tool calls), extract text
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                return item.get("text", "")
                            elif hasattr(item, "text"):
                                return item.text
                        # If no text found, stringify the content
                        return str(content)
                    return str(content)
                elif isinstance(last_message, dict):
                    content = last_message.get("content", "")
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                return item.get("text", "")
                        return str(content)
                    return str(content) if content else str(last_message)
                else:
                    return str(last_message)

            return "No response generated"
        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            raise

    def _process_result(self, result: str) -> GenerateResult:
        """Process agent result and detect terminal speak tool.

        Args:
            result: Agent output

        Returns:
            GenerateResult
        """
        from empathy.agents.tools.speak import (
            TERMINAL_SPEAK_CLOSE,
            TERMINAL_SPEAK_OPEN,
        )

        open_idx = result.find(TERMINAL_SPEAK_OPEN)
        close_idx = result.find(TERMINAL_SPEAK_CLOSE)

        if open_idx != -1 and close_idx != -1 and open_idx < close_idx:
            start = open_idx + len(TERMINAL_SPEAK_OPEN)
            content = result[start:close_idx].strip()
            return GenerateResult(type="draft", content=content)

        # Otherwise, it's a clarification
        return GenerateResult(type="clarification", content=result)

    def generate_draft(
        self,
        instruction: str,
        transcript: list[Turn],
        draft_history: list[Draft] | None = None,
        *,
        active_skills: list[Any] | None = None,
        summary: str = "",
        emotion_state: dict | None = None,
        clinical_observation: dict | None = None,
    ) -> GenerateResult:
        """Generate a draft using LangChain agent.

        Args:
            instruction: Controller instruction
            transcript: Conversation transcript
            draft_history: Draft history for feedback
            active_skills: Active skills
            summary: Conversation summary
            emotion_state: Current emotion state (client only)
            clinical_observation: Current clinical observation (therapist only)

        Returns:
            GenerateResult (draft or clarification)
        """
        try:
            # Build context using existing ContextBuilder
            ctx = self._context_builder.build(
                instruction=instruction,
                transcript=transcript,
                draft_history=draft_history or [],
                active_skills=active_skills,
                summary=summary,
                emotion_state=emotion_state,
                clinical_observation=clinical_observation,
            )

            # Combine system blocks into a single system context
            system_context = "\n\n".join(
                block.get("text", "") for block in ctx.system if block.get("text")
            )

            # Format conversation history from messages
            conversation_history = ""
            if ctx.messages:
                conversation_history = "\n\n".join(
                    f"{msg['role'].upper()}: {msg['content']}"
                    for msg in ctx.messages
                )

            # Combine instruction with conversation history
            full_instruction = instruction
            if conversation_history:
                full_instruction = f"{conversation_history}\n\nCONTROLLER: {instruction}"

            # Call agent with retry
            result = self._call_agent_with_retry(full_instruction, system_context)
            return self._process_result(result)

        except Exception as e:
            logger.error(f"LangChain agent failed: {e}")
            raise

    def _role_preamble(self) -> str:
        """Get role preamble based on side.

        Returns:
            Role preamble text
        """
        if self.side == "therapist":
            return (
                "You are a professional therapist conducting a structured counseling session. "
                "A human controller directs you via brief instructions. "
                "EVERY instruction is a dialogue directive — always generate a reply "
                "by calling the speak tool. Never treat an instruction as a question "
                "directed at you.\n\n"
                "Examples of brief instructions and what to do:\n"
                '- "hi" / "hello" → generate a warm therapeutic greeting\n'
                '- "continue" / "go ahead" → produce the natural next utterance\n'
                '- a single word or phrase (e.g. "anxiety", "deeper") → use it as a '
                "thematic cue for your next line\n"
                '- "reflect back" / "validate" → apply that therapeutic technique\n\n'
                "Rules:\n"
                "- ALWAYS call speak with your dialogue text — no stage directions, "
                "role labels, or metadata.\n"
                "- Maintain coherence with the conversation history in the messages.\n"
                "- Only ask for clarification (plain text, no speak call) when the "
                "instruction is truly ambiguous AND the conversation history provides "
                "no context to resolve it. This should be rare."
            )
        else:  # client
            return (
                "You are a client attending a therapeutic counseling session. "
                "A human controller is guiding your responses via brief instructions. "
                "Generate a single natural utterance as the client. "
                "Output ONLY the spoken text — no stage directions, role labels, or metadata."
            )
