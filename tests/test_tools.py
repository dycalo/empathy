"""Tests for Phase 2: System tools implementation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from empathy.agents.tools.emotion_state import create_emotion_state_tool
from empathy.agents.tools.listen import create_listen_tool
from empathy.agents.tools.memory_manage import create_memory_manage_tool
from empathy.agents.tools.record import create_record_tool
from empathy.agents.tools.speak import create_speak_tool
from empathy.core.models import Turn, TurnSource


class TestSpeakTool:
    """Tests for speak tool."""

    def test_speak_returns_terminal_marker(self):
        """Test that speak tool returns the terminal marker."""
        tool = create_speak_tool()
        result = tool.func(content="Hello, how are you feeling today?")

        assert result.startswith("__TERMINAL_SPEAK__:")
        assert "Hello, how are you feeling today?" in result

    def test_speak_strips_content(self):
        """Test that speak tool handles content with whitespace."""
        tool = create_speak_tool()
        result = tool.func(content="  Hello  ")

        assert "__TERMINAL_SPEAK__:  Hello  " == result

    def test_speak_tool_name(self):
        """Test that speak tool has correct name."""
        tool = create_speak_tool()
        assert tool.name == "speak"

    def test_speak_tool_description(self):
        """Test that speak tool has description."""
        tool = create_speak_tool()
        assert "Submit your dialogue turn" in tool.description
        assert "speak" in tool.description.lower()


class TestListenTool:
    """Tests for listen tool."""

    @pytest.fixture
    def transcript_file(self, tmp_path: Path) -> Path:
        """Create a temporary transcript file with test data."""
        transcript_path = tmp_path / "transcript.jsonl"

        # Create test turns
        turns = [
            Turn.create(
                speaker="therapist",
                source=TurnSource.AGENT_ACCEPT,
                content="Hello, how are you feeling today?",
            ),
            Turn.create(
                speaker="client",
                source=TurnSource.AGENT_ACCEPT,
                content="I'm feeling anxious about work.",
            ),
            Turn.create(
                speaker="therapist",
                source=TurnSource.AGENT_ACCEPT,
                content="Can you tell me more about what's making you anxious?",
            ),
            Turn.create(
                speaker="client",
                source=TurnSource.AGENT_ACCEPT,
                content="I have a big presentation coming up and I'm worried.",
            ),
            Turn.create(
                speaker="therapist",
                source=TurnSource.AGENT_ACCEPT,
                content="That sounds stressful. What specifically worries you?",
            ),
        ]

        # Write turns to file
        with transcript_path.open("w") as f:
            for turn in turns:
                f.write(json.dumps(turn.to_dict(), ensure_ascii=False) + "\n")

        return transcript_path

    def test_listen_recent_turns(self, transcript_file: Path):
        """Test reading recent turns."""
        tool = create_listen_tool(transcript_file)
        result = tool.func(scope="recent", limit=2)

        assert "[Turn 3]" in result
        assert "[Turn 4]" in result
        assert "presentation" in result
        assert "[Turn 0]" not in result

    def test_listen_all_turns(self, transcript_file: Path):
        """Test reading all turns."""
        tool = create_listen_tool(transcript_file)
        result = tool.func(scope="all")

        assert "[Turn 0]" in result
        assert "[Turn 4]" in result
        assert "Hello" in result
        assert "stressful" in result

    def test_listen_range_turns(self, transcript_file: Path):
        """Test reading a range of turns."""
        tool = create_listen_tool(transcript_file)
        result = tool.func(scope="range", start_turn=1, end_turn=3)

        assert "[Turn 1]" in result
        assert "[Turn 2]" in result
        assert "[Turn 0]" not in result
        assert "[Turn 3]" not in result

    def test_listen_search_keyword(self, transcript_file: Path):
        """Test searching for a keyword."""
        tool = create_listen_tool(transcript_file)
        result = tool.func(scope="search", keyword="anxious")

        assert "anxious" in result.lower()
        assert "[Turn 1]" in result
        assert "[Turn 2]" in result
        assert "presentation" not in result

    def test_listen_filter_by_speaker(self, transcript_file: Path):
        """Test filtering by speaker."""
        tool = create_listen_tool(transcript_file)
        result = tool.func(scope="all", speaker="client")

        assert "CLIENT:" in result
        assert "THERAPIST:" not in result
        assert "anxious" in result

    def test_listen_empty_transcript(self, tmp_path: Path):
        """Test reading from empty transcript."""
        empty_transcript = tmp_path / "empty.jsonl"
        empty_transcript.touch()

        tool = create_listen_tool(empty_transcript)
        result = tool.func(scope="all")

        assert "No conversation history" in result

    def test_listen_nonexistent_transcript(self, tmp_path: Path):
        """Test reading from nonexistent transcript."""
        nonexistent = tmp_path / "nonexistent.jsonl"

        tool = create_listen_tool(nonexistent)
        result = tool.func(scope="all")

        assert "No conversation history" in result

    def test_listen_tool_name(self, transcript_file: Path):
        """Test that listen tool has correct name."""
        tool = create_listen_tool(transcript_file)
        assert tool.name == "listen"

    def test_listen_tool_description(self, transcript_file: Path):
        """Test that listen tool has description."""
        tool = create_listen_tool(transcript_file)
        assert "conversation history" in tool.description.lower()
        assert "transcript" in tool.description.lower()


class TestRecordTool:
    """Tests for record tool (therapist only)."""

    @pytest.fixture
    def dialogue_dir(self, tmp_path: Path) -> Path:
        """Create a temporary dialogue directory."""
        dialogue_dir = tmp_path / "test_dialogue"
        dialogue_dir.mkdir()

        # Create state.json
        state_path = dialogue_dir / ".empathy" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"turn_number": 5}, ensure_ascii=False))

        return dialogue_dir

    def test_record_create(self, dialogue_dir: Path):
        """Test creating a clinical record."""
        tool = create_record_tool(dialogue_dir)
        result = tool.func(
            action="create",
            record_type="assessment",
            content="Client presents with moderate anxiety symptoms.",
        )

        assert "Record created:" in result
        # Extract record ID
        record_id = result.split(": ")[1]

        # Verify file was created
        records_dir = dialogue_dir / ".empathy" / "therapist" / "records" / "assessments"
        record_files = list(records_dir.glob(f"*_{record_id}.json"))
        assert len(record_files) == 1

        # Verify content
        record_data = json.loads(record_files[0].read_text())
        assert record_data["id"] == record_id
        assert record_data["type"] == "assessment"
        assert record_data["content"] == "Client presents with moderate anxiety symptoms."
        assert record_data["turn_number"] == 5

    def test_record_read(self, dialogue_dir: Path):
        """Test reading a clinical record."""
        tool = create_record_tool(dialogue_dir)

        # Create a record first
        create_result = tool.func(
            action="create",
            record_type="progress_note",
            content="Client showed improvement in coping strategies.",
        )
        record_id = create_result.split(": ")[1]

        # Read the record
        read_result = tool.func(action="read", record_type="progress_note", record_id=record_id)

        assert record_id in read_result
        assert "improvement in coping strategies" in read_result

    def test_record_update(self, dialogue_dir: Path):
        """Test updating a clinical record."""
        tool = create_record_tool(dialogue_dir)

        # Create a record first
        create_result = tool.func(
            action="create",
            record_type="treatment_plan",
            content="Initial treatment plan: CBT for anxiety.",
        )
        record_id = create_result.split(": ")[1]

        # Update the record
        update_result = tool.func(
            action="update",
            record_type="treatment_plan",
            record_id=record_id,
            content="Updated treatment plan: CBT + mindfulness exercises.",
        )

        assert f"Record updated: {record_id}" in update_result

        # Verify update
        read_result = tool.func(action="read", record_type="treatment_plan", record_id=record_id)
        assert "mindfulness exercises" in read_result
        assert "updated_at" in read_result

    def test_record_list(self, dialogue_dir: Path):
        """Test listing clinical records."""
        tool = create_record_tool(dialogue_dir)

        # Create multiple records
        tool.func(
            action="create",
            record_type="observation",
            content="Client appeared tense during session.",
        )
        tool.func(
            action="create",
            record_type="observation",
            content="Client made good eye contact today.",
        )

        # List records
        list_result = tool.func(action="list", record_type="observation")

        assert "tense during session" in list_result
        assert "good eye contact" in list_result
        assert "observation" in list_result

    def test_record_create_missing_content(self, dialogue_dir: Path):
        """Test creating record without content."""
        tool = create_record_tool(dialogue_dir)
        result = tool.func(action="create", record_type="assessment")

        assert "Content is required" in result

    def test_record_read_missing_id(self, dialogue_dir: Path):
        """Test reading record without ID."""
        tool = create_record_tool(dialogue_dir)
        result = tool.func(action="read", record_type="assessment")

        assert "Record ID is required" in result

    def test_record_read_nonexistent(self, dialogue_dir: Path):
        """Test reading nonexistent record."""
        tool = create_record_tool(dialogue_dir)
        result = tool.func(action="read", record_type="assessment", record_id="nonexistent-id")

        assert "Record not found" in result

    def test_record_list_empty(self, dialogue_dir: Path):
        """Test listing when no records exist."""
        tool = create_record_tool(dialogue_dir)
        result = tool.func(action="list", record_type="assessment")

        assert "No records found" in result

    def test_record_tool_name(self, dialogue_dir: Path):
        """Test that record tool has correct name."""
        tool = create_record_tool(dialogue_dir)
        assert tool.name == "record"

    def test_record_tool_description(self, dialogue_dir: Path):
        """Test that record tool has description."""
        tool = create_record_tool(dialogue_dir)
        assert "clinical records" in tool.description.lower()
        assert "therapist" in tool.description.lower()


class TestEmotionStateTool:
    """Tests for emotion_state tool (client only)."""

    @pytest.fixture
    def dialogue_dir(self, tmp_path: Path) -> Path:
        """Create a temporary dialogue directory."""
        dialogue_dir = tmp_path / "test_dialogue"
        dialogue_dir.mkdir()

        # Create state.json
        state_path = dialogue_dir / ".empathy" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"turn_number": 3}, ensure_ascii=False))

        return dialogue_dir

    def test_emotion_state_update(self, dialogue_dir: Path):
        """Test updating emotion state."""
        tool = create_emotion_state_tool(dialogue_dir)
        result = tool.func(
            action="update",
            primary_emotion="anxious",
            intensity=7,
            triggers=["upcoming presentation", "fear of judgment"],
            physical_sensations=["tight chest", "rapid heartbeat"],
            thoughts="Everyone will think I'm incompetent",
        )

        assert "Emotion state updated" in result
        assert "anxious" in result
        assert "7/10" in result

        # Verify current.json was created
        current_path = dialogue_dir / ".empathy" / "client" / "emotion-states" / "current.json"
        assert current_path.exists()

        current_data = json.loads(current_path.read_text())
        assert current_data["primary_emotion"] == "anxious"
        assert current_data["intensity"] == 7
        assert "upcoming presentation" in current_data["triggers"]
        assert current_data["turn_number"] == 3

        # Verify history.jsonl was created
        history_path = dialogue_dir / ".empathy" / "client" / "emotion-states" / "history.jsonl"
        assert history_path.exists()

    def test_emotion_state_read(self, dialogue_dir: Path):
        """Test reading current emotion state."""
        tool = create_emotion_state_tool(dialogue_dir)

        # Update first
        tool.func(
            action="update",
            primary_emotion="sad",
            intensity=5,
            thoughts="I feel overwhelmed",
        )

        # Read current state
        result = tool.func(action="read")

        assert "sad" in result
        assert "5" in result
        assert "overwhelmed" in result

    def test_emotion_state_history(self, dialogue_dir: Path):
        """Test viewing emotion state history."""
        tool = create_emotion_state_tool(dialogue_dir)

        # Create multiple states
        tool.func(action="update", primary_emotion="anxious", intensity=8)
        tool.func(action="update", primary_emotion="sad", intensity=6)
        tool.func(action="update", primary_emotion="calm", intensity=3)

        # View history
        result = tool.func(action="history")

        assert "anxious" in result
        assert "sad" in result
        assert "calm" in result
        assert "[Turn 3]" in result

    def test_emotion_state_update_missing_emotion(self, dialogue_dir: Path):
        """Test updating without primary emotion."""
        tool = create_emotion_state_tool(dialogue_dir)
        result = tool.func(action="update", intensity=5)

        assert "Primary emotion is required" in result

    def test_emotion_state_update_missing_intensity(self, dialogue_dir: Path):
        """Test updating without intensity."""
        tool = create_emotion_state_tool(dialogue_dir)
        result = tool.func(action="update", primary_emotion="anxious")

        assert "Intensity is required" in result

    def test_emotion_state_read_empty(self, dialogue_dir: Path):
        """Test reading when no state exists."""
        tool = create_emotion_state_tool(dialogue_dir)
        result = tool.func(action="read")

        assert "No current emotion state" in result

    def test_emotion_state_history_empty(self, dialogue_dir: Path):
        """Test viewing history when empty."""
        tool = create_emotion_state_tool(dialogue_dir)
        result = tool.func(action="history")

        assert "No emotion history" in result

    def test_emotion_state_tool_name(self, dialogue_dir: Path):
        """Test that emotion_state tool has correct name."""
        tool = create_emotion_state_tool(dialogue_dir)
        assert tool.name == "emotion_state"

    def test_emotion_state_tool_description(self, dialogue_dir: Path):
        """Test that emotion_state tool has description."""
        tool = create_emotion_state_tool(dialogue_dir)
        assert "emotional state" in tool.description.lower()
        assert "client" in tool.description.lower()


class TestMemoryManageTool:
    """Tests for memory_manage tool."""

    @pytest.fixture
    def dialogue_dir(self, tmp_path: Path) -> Path:
        """Create a temporary dialogue directory."""
        dialogue_dir = tmp_path / "test_dialogue"
        dialogue_dir.mkdir()
        return dialogue_dir

    def test_memory_store(self, dialogue_dir: Path):
        """Test storing a memory."""
        tool = create_memory_manage_tool("therapist", dialogue_dir)
        result = tool.func(
            action="store",
            memory_type="pattern",
            content="Client tends to catastrophize when discussing work",
            importance=8,
        )

        assert "Memory stored:" in result
        # Extract memory ID
        memory_id = result.split(": ")[1]

        # Verify file was created
        memory_path = dialogue_dir / ".empathy" / "therapist" / "memories" / "patterns" / f"{memory_id}.json"
        assert memory_path.exists()

        # Verify content
        memory_data = json.loads(memory_path.read_text())
        assert memory_data["id"] == memory_id
        assert memory_data["type"] == "pattern"
        assert memory_data["content"] == "Client tends to catastrophize when discussing work"
        assert memory_data["importance"] == 8

        # Verify index was updated
        index_path = dialogue_dir / ".empathy" / "therapist" / "memories" / "index.json"
        assert index_path.exists()
        index_data = json.loads(index_path.read_text())
        assert any(m["id"] == memory_id for m in index_data["memories"])

    def test_memory_retrieve(self, dialogue_dir: Path):
        """Test retrieving a memory."""
        tool = create_memory_manage_tool("client", dialogue_dir)

        # Store a memory first
        store_result = tool.func(
            action="store",
            memory_type="key_event",
            content="First panic attack happened during a team meeting",
            importance=9,
        )
        memory_id = store_result.split(": ")[1]

        # Retrieve the memory
        retrieve_result = tool.func(
            action="retrieve",
            memory_type="key_event",
            memory_id=memory_id,
        )

        assert memory_id in retrieve_result
        assert "panic attack" in retrieve_result
        assert "team meeting" in retrieve_result

    def test_memory_search(self, dialogue_dir: Path):
        """Test searching memories."""
        tool = create_memory_manage_tool("therapist", dialogue_dir)

        # Store multiple memories
        tool.func(
            action="store",
            memory_type="insight",
            content="Client's anxiety is rooted in fear of judgment",
            importance=7,
        )
        tool.func(
            action="store",
            memory_type="insight",
            content="Client shows progress in self-compassion exercises",
            importance=6,
        )
        tool.func(
            action="store",
            memory_type="pattern",
            content="Client avoids eye contact when discussing family",
            importance=5,
        )

        # Search for "anxiety"
        search_result = tool.func(
            action="search",
            memory_type="insight",
            query="anxiety",
        )

        assert "anxiety" in search_result.lower()
        assert "fear of judgment" in search_result
        assert "importance: 7" in search_result

    def test_memory_update(self, dialogue_dir: Path):
        """Test updating a memory."""
        tool = create_memory_manage_tool("therapist", dialogue_dir)

        # Store a memory first
        store_result = tool.func(
            action="store",
            memory_type="relationship",
            content="Client has strained relationship with mother",
            importance=6,
        )
        memory_id = store_result.split(": ")[1]

        # Update the memory
        update_result = tool.func(
            action="update",
            memory_type="relationship",
            memory_id=memory_id,
            content="Client has strained but improving relationship with mother",
        )

        assert f"Memory updated: {memory_id}" in update_result

        # Verify update
        retrieve_result = tool.func(
            action="retrieve",
            memory_type="relationship",
            memory_id=memory_id,
        )
        assert "improving relationship" in retrieve_result
        assert "updated_at" in retrieve_result

    def test_memory_delete(self, dialogue_dir: Path):
        """Test deleting a memory."""
        tool = create_memory_manage_tool("client", dialogue_dir)

        # Store a memory first
        store_result = tool.func(
            action="store",
            memory_type="key_event",
            content="Temporary memory to be deleted",
            importance=3,
        )
        memory_id = store_result.split(": ")[1]

        # Delete the memory
        delete_result = tool.func(
            action="delete",
            memory_type="key_event",
            memory_id=memory_id,
        )

        assert f"Memory deleted: {memory_id}" in delete_result

        # Verify deletion
        memory_path = dialogue_dir / ".empathy" / "client" / "memories" / "key_events" / f"{memory_id}.json"
        assert not memory_path.exists()

    def test_memory_store_missing_content(self, dialogue_dir: Path):
        """Test storing memory without content."""
        tool = create_memory_manage_tool("therapist", dialogue_dir)
        result = tool.func(action="store", memory_type="pattern")

        assert "Content is required" in result

    def test_memory_retrieve_missing_id(self, dialogue_dir: Path):
        """Test retrieving memory without ID."""
        tool = create_memory_manage_tool("therapist", dialogue_dir)
        result = tool.func(action="retrieve", memory_type="pattern")

        assert "Memory ID is required" in result

    def test_memory_search_missing_query(self, dialogue_dir: Path):
        """Test searching without query."""
        tool = create_memory_manage_tool("therapist", dialogue_dir)
        result = tool.func(action="search", memory_type="pattern")

        assert "Query is required" in result

    def test_memory_search_no_matches(self, dialogue_dir: Path):
        """Test searching with no matches."""
        tool = create_memory_manage_tool("therapist", dialogue_dir)

        # Store a memory
        tool.func(
            action="store",
            memory_type="insight",
            content="Client shows resilience",
            importance=5,
        )

        # Search for non-matching term
        result = tool.func(action="search", memory_type="insight", query="nonexistent")

        assert "No matching memories" in result

    def test_memory_tool_name(self, dialogue_dir: Path):
        """Test that memory_manage tool has correct name."""
        tool = create_memory_manage_tool("therapist", dialogue_dir)
        assert tool.name == "memory_manage"

    def test_memory_tool_description(self, dialogue_dir: Path):
        """Test that memory_manage tool has description."""
        tool = create_memory_manage_tool("therapist", dialogue_dir)
        assert "memory" in tool.description.lower()
        assert "storage" in tool.description.lower()
