"""LLM agents for empathy.

The primary agent implementation is LangChainAgent, which uses LangChain's
agent framework for tool orchestration and dialogue generation.

Deprecated:
- BaseAgent: Removed in favor of LangChainAgent
- ClientAgent: Removed in favor of LangChainAgent(side="client")
- TherapistAgent: Removed in favor of LangChainAgent(side="therapist")
"""

from empathy.agents.langchain_agent import GenerateResult, LangChainAgent

__all__ = ["LangChainAgent", "GenerateResult"]

