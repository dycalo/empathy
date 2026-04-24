"""LangChain callbacks for Empathy agents.

Provides error handling, logging, and observability for agent execution.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


class EmpathyCallbackHandler(BaseCallbackHandler):
    """Callback handler for Empathy agents.

    Handles:
    - Tool execution errors
    - Agent action logging
    - Performance monitoring
    """

    def __init__(self, verbose: bool = False) -> None:
        """Initialize callback handler.

        Args:
            verbose: Whether to log debug information
        """
        super().__init__()
        self.verbose = verbose

    def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """Log when a tool starts executing.

        Args:
            serialized: Tool serialization
            input_str: Tool input
            **kwargs: Additional arguments
        """
        if self.verbose:
            tool_name = serialized.get("name", "unknown")
            logger.debug(f"Tool started: {tool_name} with input: {input_str[:100]}")

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Log when a tool finishes executing.

        Args:
            output: Tool output
            **kwargs: Additional arguments
        """
        if self.verbose:
            logger.debug(f"Tool finished with output: {output[:100]}")

    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        """Handle tool execution errors.

        Args:
            error: The exception that occurred
            **kwargs: Additional arguments (may include 'tool' name)
        """
        tool_name = kwargs.get("tool", "unknown")
        logger.error(f"Tool '{tool_name}' failed: {error}")

        # Return friendly error message to agent
        # Note: This doesn't actually return - it just logs
        # The agent will receive the exception through normal flow

    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        """Log agent actions for debugging.

        Args:
            action: The agent action
            **kwargs: Additional arguments
        """
        if self.verbose:
            tool_name = getattr(action, "tool", "unknown")
            tool_input = getattr(action, "tool_input", {})
            logger.debug(f"Agent action: {tool_name} with input {tool_input}")

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
        """Log when agent finishes.

        Args:
            finish: Agent finish object
            **kwargs: Additional arguments
        """
        if self.verbose:
            logger.debug("Agent finished execution")

    def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any
    ) -> None:
        """Log when LLM starts.

        Args:
            serialized: LLM serialization
            prompts: Input prompts
            **kwargs: Additional arguments
        """
        if self.verbose:
            logger.debug(f"LLM started with {len(prompts)} prompt(s)")

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Log when LLM finishes.

        Args:
            response: LLM response
            **kwargs: Additional arguments
        """
        if self.verbose:
            logger.debug("LLM finished")

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Handle LLM errors.

        Args:
            error: The exception that occurred
            **kwargs: Additional arguments
        """
        logger.error(f"LLM error: {error}")

    def on_chain_start(
        self, serialized: dict[str, Any], inputs: dict[str, Any], **kwargs: Any
    ) -> None:
        """Log when chain starts.

        Args:
            serialized: Chain serialization
            inputs: Chain inputs
            **kwargs: Additional arguments
        """
        if self.verbose:
            logger.debug("Chain started")

    def on_chain_end(self, outputs: dict[str, Any], **kwargs: Any) -> None:
        """Log when chain finishes.

        Args:
            outputs: Chain outputs
            **kwargs: Additional arguments
        """
        if self.verbose:
            logger.debug("Chain finished")

    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        """Handle chain errors.

        Args:
            error: The exception that occurred
            **kwargs: Additional arguments
        """
        logger.error(f"Chain error: {error}")
