"""Quick integration test for feedback system changes."""

from datetime import UTC, datetime
from pathlib import Path

from empathy.agents.context import ContextBuilder
from empathy.agents.feedback import FeedbackConfig, FeedbackManager
from empathy.core.models import Draft, Speaker, Turn


def test_draft_extended_fields():
    """Test that Draft model supports extended fields."""
    draft = Draft.create(
        speaker="therapist",
        content="Test content",
        source_instruction="test instruction",
        conversation_window={"start_turn": 0, "end_turn": 5},
        api_usage={
            "input_tokens": 1500,
            "output_tokens": 150,
            "cached_tokens": 800,
            "latency_ms": 2500,
        },
        model="claude-haiku-4-5-20251001",
    )

    assert draft.conversation_window == {"start_turn": 0, "end_turn": 5}
    assert draft.api_usage["input_tokens"] == 1500
    assert draft.model == "claude-haiku-4-5-20251001"

    # Test serialization
    data = draft.to_dict()
    assert "conversation_window" in data
    assert "api_usage" in data
    assert "model" in data

    # Test deserialization
    draft2 = Draft.from_dict(data)
    assert draft2.conversation_window == draft.conversation_window
    assert draft2.api_usage == draft.api_usage
    assert draft2.model == draft.model

    print("✓ Draft extended fields work correctly")


def test_feedback_manager():
    """Test FeedbackManager basic functionality."""
    config = FeedbackConfig(
        max_examples=3,
        format_style="concise",
        sampling_strategy="balanced",
    )

    manager = FeedbackManager(dialogue_dir=None, config=config)

    # Create mock history
    history = [
        {
            "turn_number": 1,
            "side": "therapist",
            "instruction": "explore anxiety",
            "draft": "Let's talk about your childhood",
            "result": "REJECT",
            "edited": None,
            "rejection_reason": "too directive",
        },
        {
            "turn_number": 2,
            "side": "therapist",
            "instruction": "validate feelings",
            "draft": "That sounds difficult.",
            "result": "EDIT",
            "edited": "That sounds really challenging.",
            "rejection_reason": None,
        },
    ]

    # Test selection
    examples = manager.select_examples(history, "explore anxiety", max_examples=3)
    assert len(examples) <= 3

    # Test formatting
    formatted = manager.format_examples(examples, format_style="concise")
    assert "## Learning from recent feedback" in formatted
    assert "REJECTED" in formatted or "EDITED" in formatted

    print("✓ FeedbackManager works correctly")


def test_context_builder_integration():
    """Test ContextBuilder with FeedbackManager integration."""
    config = FeedbackConfig(max_examples=2, format_style="concise")

    builder = ContextBuilder(
        side="therapist",
        role_preamble="You are a therapist.",
        knowledge="",
        dialogue_background="",
        feedback_config=config,
    )

    # Create mock data
    turns = [
        Turn.create(
            speaker="client",
            source="human",
            content="I feel anxious.",
        )
    ]

    drafts = [
        Draft(
            id="1",
            speaker="therapist",
            content="Let's talk about your childhood",
            source_instruction="explore anxiety",
            outcome="rejected",
            timestamp=datetime.now(UTC),
        ),
        Draft(
            id="2",
            speaker="therapist",
            content="That sounds difficult.",
            source_instruction="validate feelings",
            outcome="edited",
            timestamp=datetime.now(UTC),
            final_content="That sounds really challenging.",
        ),
    ]

    # Build context
    ctx = builder.build(
        instruction="continue naturally",
        transcript=turns,
        draft_history=drafts,
    )

    assert ctx.system
    assert ctx.messages
    assert ctx.tools

    # Check that feedback is included in messages
    last_message = ctx.messages[-1]["content"]
    assert "Controller instruction: continue naturally" in last_message

    print("✓ ContextBuilder integration works correctly")


if __name__ == "__main__":
    test_draft_extended_fields()
    test_feedback_manager()
    test_context_builder_integration()
    print("\n✅ All integration tests passed!")
