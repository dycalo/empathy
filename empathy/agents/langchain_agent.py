"""LangChain-based agent implementation for Empathy.

This module provides a LangChain-powered alternative to BaseAgent,
with enhanced tool management, error handling, and retry mechanisms.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from empathy.agents.base import BaseAgent, GenerateResult
from empathy.agents.callbacks import EmpathyCallbackHandler
from empathy.agents.tools import create_all_tools
from empathy.core.models import Draft, Speaker, Turn

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.environ.get("EMPATHY_MODEL")


class LangChainAgent:
    """LangChain-powered agent for dialogue generation.

    This agent uses LangChain's AgentExecutor to manage tool calls,
    with automatic retry, error handling, and fallback to BaseAgent.
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
            verbose: Enable verbose logging
        """
        self.side = side
        self.model = model
        self.max_tokens = max_tokens
        self.verbose = verbose
        self.dialogue_dir = dialogue_dir
        self.transcript_path = transcript_path

        # Initialize BaseAgent as fallback
        self.base_agent = BaseAgent(
            side=side,
            model=model,
            knowledge=knowledge,
            dialogue_background=dialogue_background,
            api_key=api_key,
            max_tokens=max_tokens,
            mcp_provider=mcp_provider,
        )

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

        # Initialize callback handler
        self.callback_handler = EmpathyCallbackHandler(verbose=verbose)

        # Context builder (reuse from BaseAgent)
        self._context_builder = self.base_agent._context_builder

        # Agent executor (initialized lazily)
        self._agent_graph: Any | None = None
        self._mcp_provider = mcp_provider

    def _initialize_agent_executor(self) -> Any:
        """Initialize LangChain agent graph.

        Returns:
            Configured agent graph
        """
        # Create tools
        tools = create_all_tools(
            side=self.side,
            dialogue_dir=self.dialogue_dir,
            transcript_path=self.transcript_path,
            mcp_provider=self._mcp_provider,
        )

        # Create system prompt based on side
        if self.side == "therapist":
            system_prompt = (
                "You are a therapist in a counseling session. "
                "Use the available tools to manage clinical records, "
                "review conversation history, and provide therapeutic responses. "
                "When ready to speak, use the 'speak' tool."
            )
        else:  # client
            system_prompt = (
                "You are a client in a counseling session. "
                "Use the available tools to track your emotions, "
                "review conversation history, and express your thoughts. "
                "When ready to speak, use the 'speak' tool."
            )

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
    def _call_agent_with_retry(self, instruction: str) -> str:
        """Call agent with automatic retry on transient failures.

        Args:
            instruction: Controller instruction

        Returns:
            Agent output

        Raises:
            Exception: If all retries fail
        """
        if self._agent_graph is None:
            self._agent_graph = self._initialize_agent_executor()

        try:
            # Invoke agent graph with new API
            result = self._agent_graph.invoke({"messages": [("user", instruction)]})

            # Extract the final message
            messages = result.get("messages", [])
            if messages:
                last_message = messages[-1]
                # Handle different message types
                if hasattr(last_message, "content"):
                    return last_message.content
                elif isinstance(last_message, dict):
                    return last_message.get("content", str(last_message))
                else:
                    return str(last_message)

            return "No response generated"
        except Exception as e:
            logger.warning(f"Agent execution failed, retrying: {e}")
            raise

    def _process_result(self, result: str) -> GenerateResult:
        """Process agent result and detect terminal speak tool.

        Args:
            result: Agent output

        Returns:
            GenerateResult
        """
        # Check for terminal speak marker
        if result.startswith("__TERMINAL_SPEAK__:"):
            content = result.replace("__TERMINAL_SPEAK__:", "").strip()
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
    ) -> GenerateResult:
        """Generate a draft using LangChain agent.

        Args:
            instruction: Controller instruction
            transcript: Conversation transcript
            draft_history: Draft history for feedback
            active_skills: Active skills
            summary: Conversation summary

        Returns:
            GenerateResult (draft or clarification)
        """
        try:
            # Build context using existing ContextBuilder
            # This ensures system prompt and messages are consistent
            ctx = self._context_builder.build(
                instruction=instruction,
                transcript=transcript,
                draft_history=draft_history or [],
                active_skills=active_skills,
                summary=summary,
            )

            # For now, we'll use a simplified approach:
            # Pass the instruction directly to the agent
            # TODO: In Phase 5, integrate ctx.system and ctx.messages
            # into LangChain's prompt template

            result = self._call_agent_with_retry(instruction)
            return self._process_result(result)

        except Exception as e:
            logger.error(f"LangChain agent failed, falling back to BaseAgent: {e}")

            # Fallback to BaseAgent
            return self.base_agent.generate_draft(
                instruction=instruction,
                transcript=transcript,
                draft_history=draft_history,
                active_skills=active_skills,
                summary=summary,
            )

    def summarize(self, turns: list[Turn], previous_summary: str = "") -> str:
        """Generate summary of conversation turns.

        Delegates to BaseAgent for now.

        Args:
            turns: Turns to summarize
            previous_summary: Previous summary to build on

        Returns:
            Summary text
        """
        return self.base_agent.summarize(turns, previous_summary)

    def _role_preamble(self) -> str:
        """Get role preamble.

        Delegates to BaseAgent.

        Returns:
            Role preamble text
        """
        return self.base_agent._role_preamble()
