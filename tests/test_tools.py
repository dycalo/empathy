"""Tests for Phase 2: System tools implementation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from empathy.agents.tools.emotion_state import create_emotion_state_tool
from empathy.agents.tools.memory_manage import create_memory_manage_tool
from empathy.agents.tools.record import create_record_tool
from empathy.agents.tools.speak import create_speak_tool


class TestSpeakTool:
    """Tests for speak tool."""

    def test_speak_returns_xml_marker(self):
        """Test that speak tool returns the XML terminal marker."""
        from empathy.agents.tools.speak import (
            TERMINAL_SPEAK_CLOSE,
            TERMINAL_SPEAK_OPEN,
        )

        tool = create_speak_tool()
        result = tool.func(content="Hello, how are you feeling today?")

        assert result.startswith(TERMINAL_SPEAK_OPEN)
        assert result.endswith(TERMINAL_SPEAK_CLOSE)
        assert "Hello, how are you feeling today?" in result

    def test_speak_preserves_content_whitespace(self):
        """Test that speak tool preserves content whitespace inside XML tags."""
        from empathy.agents.tools.speak import (
            TERMINAL_SPEAK_CLOSE,
            TERMINAL_SPEAK_OPEN,
        )

        tool = create_speak_tool()
        result = tool.func(content="  Hello  ")

        assert result == f"{TERMINAL_SPEAK_OPEN}  Hello  {TERMINAL_SPEAK_CLOSE}"

    def test_speak_rejects_empty_content(self):
        """Test that speak tool rejects empty content."""
        tool = create_speak_tool()
        with pytest.raises(ValueError, match="Content cannot be empty"):
            tool.func(content="")

    def test_speak_tool_name(self):
        """Test that speak tool has correct name."""
        tool = create_speak_tool()
        assert tool.name == "speak"

    def test_speak_tool_description(self):
        """Test that speak tool has description."""
        tool = create_speak_tool()
        assert "Submit your dialogue turn" in tool.description
        assert "speak" in tool.description.lower()

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
    """Tests for memory_manage tool (user-level, repository-backed)."""

    _USER_ID = "test_user"

    @pytest.fixture(autouse=True)
    def _reset_repo(self):
        """Reset global repository after each test."""
        from empathy.storage.memory_repo import set_memory_repository

        set_memory_repository(None)
        yield
        set_memory_repository(None)

    @pytest.fixture
    def repo(self):
        """Create a fresh in-memory repository."""
        from empathy.storage.memory_repo import (
            InMemoryMemoryRepository,
            set_memory_repository,
        )

        r = InMemoryMemoryRepository()
        set_memory_repository(r)
        return r

    @pytest.fixture
    def tool(self, repo):
        """Create memory_manage tool backed by the in-memory repo."""
        return create_memory_manage_tool(self._USER_ID)

    def test_memory_store(self, tool, repo):
        """Test storing a memory."""
        result = tool.func(
            action="store",
            memory_type="pattern",
            content="Client tends to catastrophize when discussing work",
            importance=8,
        )

        assert "Memory stored:" in result
        memory_id = result.split(": ")[1]

        # Verify via repository
        mem = repo.retrieve(self._USER_ID, memory_id)
        assert mem is not None
        assert mem.type == "pattern"
        assert mem.content == "Client tends to catastrophize when discussing work"
        assert mem.importance == 8

    def test_memory_retrieve(self, tool, repo):
        """Test retrieving a memory."""
        store_result = tool.func(
            action="store",
            memory_type="key_event",
            content="First panic attack happened during a team meeting",
            importance=9,
        )
        memory_id = store_result.split(": ")[1]

        retrieve_result = tool.func(
            action="retrieve",
            memory_type="key_event",
            memory_id=memory_id,
        )

        assert memory_id in retrieve_result
        assert "panic attack" in retrieve_result
        assert "team meeting" in retrieve_result

    def test_memory_search(self, tool):
        """Test searching memories."""
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

        search_result = tool.func(
            action="search",
            memory_type="insight",
            query="anxiety",
        )

        assert "anxiety" in search_result.lower()
        assert "fear of judgment" in search_result
        assert "importance: 7" in search_result

    def test_memory_update(self, tool):
        """Test updating a memory."""
        store_result = tool.func(
            action="store",
            memory_type="relationship",
            content="Client has strained relationship with mother",
            importance=6,
        )
        memory_id = store_result.split(": ")[1]

        update_result = tool.func(
            action="update",
            memory_type="relationship",
            memory_id=memory_id,
            content="Client has strained but improving relationship with mother",
        )

        assert f"Memory updated: {memory_id}" in update_result

        retrieve_result = tool.func(
            action="retrieve",
            memory_type="relationship",
            memory_id=memory_id,
        )
        assert "improving relationship" in retrieve_result
        assert "Updated:" in retrieve_result

    def test_memory_delete(self, tool, repo):
        """Test deleting a memory."""
        store_result = tool.func(
            action="store",
            memory_type="key_event",
            content="Temporary memory to be deleted",
            importance=3,
        )
        memory_id = store_result.split(": ")[1]

        delete_result = tool.func(
            action="delete",
            memory_type="key_event",
            memory_id=memory_id,
        )

        assert f"Memory deleted: {memory_id}" in delete_result
        assert repo.retrieve(self._USER_ID, memory_id) is None

    def test_memory_store_missing_content(self, tool):
        """Test storing memory without content."""
        result = tool.func(action="store", memory_type="pattern")
        assert "Content is required" in result

    def test_memory_retrieve_missing_id(self, tool):
        """Test retrieving memory without ID."""
        result = tool.func(action="retrieve", memory_type="pattern")
        assert "Memory ID is required" in result

    def test_memory_search_missing_query(self, tool):
        """Test searching without query."""
        result = tool.func(action="search", memory_type="pattern")
        assert "Query is required" in result

    def test_memory_search_no_matches(self, tool):
        """Test searching with no matches."""
        tool.func(
            action="store",
            memory_type="insight",
            content="Client shows resilience",
            importance=5,
        )

        result = tool.func(action="search", memory_type="insight", query="nonexistent")
        assert "No matching memories" in result

    def test_memory_tool_name(self, tool):
        """Test that memory_manage tool has correct name."""
        assert tool.name == "memory_manage"

    def test_memory_tool_description(self, tool):
        """Test that memory_manage tool has description."""
        assert "memory" in tool.description.lower()
        assert "storage" in tool.description.lower()

    def test_memory_manage_returns_none_without_user_id(self):
        """Test that tool creation returns None when user_id is missing."""
        assert create_memory_manage_tool(None) is None
