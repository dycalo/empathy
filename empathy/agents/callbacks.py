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
    - Execution statistics
    """

    def __init__(self, verbose: bool = False) -> None:
        """Initialize callback handler.

        Args:
            verbose: Whether to log debug information
        """
        super().__init__()
        self.verbose = verbose
        self._tool_call_count = 0
        self._error_count = 0

    def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """Log when a tool starts executing.

        Args:
            serialized: Tool serialization
            input_str: Tool input
            **kwargs: Additional arguments
        """
        tool_name = serialized.get("name", "unknown")
        self._tool_call_count += 1

        if self.verbose:
            logger.info(f"[Tool Start] {tool_name}")
            logger.debug(f"  Input: {input_str[:100]}...")

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Log when a tool finishes executing.

        Args:
            output: Tool output
            **kwargs: Additional arguments
        """
        if self.verbose:
            logger.info(f"[Tool End] Output length: {len(output)}")
            logger.debug(f"  Output: {output[:100]}...")

    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        """Handle tool execution errors.

        Args:
            error: The exception that occurred
            **kwargs: Additional arguments (may include 'tool' name)
        """
        tool_name = kwargs.get("tool", "unknown")
        self._error_count += 1

        logger.error(f"[Tool Error] {tool_name}: {error}")

        if self.verbose:
            logger.debug(f"  Error details: {error}", exc_info=True)

    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        """Log agent actions for debugging.

        Args:
            action: The agent action
            **kwargs: Additional arguments
        """
        if self.verbose:
            tool_name = getattr(action, "tool", "unknown")
            tool_input = getattr(action, "tool_input", {})
            logger.info(f"[Agent Action] Tool: {tool_name}")
            logger.debug(f"  Input: {tool_input}")

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
        """Log when agent finishes.

        Args:
            finish: Agent finish object
            **kwargs: Additional arguments
        """
        if self.verbose:
            logger.info(
                f"[Agent Finish] Tools called: {self._tool_call_count}, "
                f"Errors: {self._error_count}"
            )

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
            logger.info(f"[LLM Start] Prompts: {len(prompts)}")
            for i, prompt in enumerate(prompts[:2]):  # Log first 2 prompts
                logger.debug(f"  Prompt {i}: {prompt[:200]}...")

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Log when LLM finishes.

        Args:
            response: LLM response
            **kwargs: Additional arguments
        """
        if self.verbose:
            logger.info("[LLM End] Generation complete")

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Handle LLM errors.

        Args:
            error: The exception that occurred
            **kwargs: Additional arguments
        """
        self._error_count += 1
        logger.error(f"[LLM Error] {error}")

        if self.verbose:
            logger.debug(f"  Error details: {error}", exc_info=True)

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
            chain_name = serialized.get("name", "unknown")
            logger.info(f"[Chain Start] {chain_name}")

    def on_chain_end(self, outputs: dict[str, Any], **kwargs: Any) -> None:
        """Log when chain finishes.

        Args:
            outputs: Chain outputs
            **kwargs: Additional arguments
        """
        if self.verbose:
            logger.info("[Chain End] Execution complete")

    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        """Handle chain errors.

        Args:
            error: The exception that occurred
            **kwargs: Additional arguments
        """
        self._error_count += 1
        logger.error(f"[Chain Error] {error}")

        if self.verbose:
            logger.debug(f"  Error details: {error}", exc_info=True)

    def get_stats(self) -> dict[str, int]:
        """Get execution statistics.

        Returns:
            Dictionary with tool_calls and errors counts
        """
        return {
            "tool_calls": self._tool_call_count,
            "errors": self._error_count,
        }

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._tool_call_count = 0
        self._error_count = 0

