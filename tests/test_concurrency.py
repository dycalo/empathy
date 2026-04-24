"""Concurrency tests for file locking in tools."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from empathy.agents.tools.emotion_state import create_emotion_state_tool
from empathy.agents.tools.listen import create_listen_tool
from empathy.core.models import Turn, TurnSource


class TestConcurrentFileAccess:
    """Tests for concurrent file access with fcntl locks."""

    @pytest.fixture
    def transcript_file(self, tmp_path: Path) -> Path:
        """Create a transcript file with test data."""
        transcript_path = tmp_path / "transcript.jsonl"

        # Create test turns
        turns = [
            Turn.create(
                speaker="therapist",
                source=TurnSource.AGENT_ACCEPT,
                content=f"Turn {i}",
            )
            for i in range(10)
        ]

        # Write turns to file
        with transcript_path.open("w") as f:
            for turn in turns:
                f.write(json.dumps(turn.to_dict(), ensure_ascii=False) + "\n")

        return transcript_path

    @pytest.fixture
    def dialogue_dir(self, tmp_path: Path) -> Path:
        """Create a dialogue directory."""
        dialogue_dir = tmp_path / "test_dialogue"
        dialogue_dir.mkdir()

        # Create state.json
        state_path = dialogue_dir / ".empathy" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"turn_number": 1}, ensure_ascii=False))

        return dialogue_dir

    def test_concurrent_listen_reads(self, transcript_file: Path):
        """Test multiple concurrent reads with shared locks."""
        tool = create_listen_tool(transcript_file)

        def read_transcript(reader_id: int) -> tuple[int, str]:
            """Read transcript and return reader ID and result."""
            result = tool.func(scope="all")
            return (reader_id, result)

        # Run 10 concurrent reads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_transcript, i) for i in range(10)]
            results = [future.result() for future in as_completed(futures)]

        # All reads should succeed
        assert len(results) == 10
        for reader_id, result in results:
            assert "Turn 0" in result
            assert "Turn 9" in result

    def test_concurrent_emotion_state_writes(self, dialogue_dir: Path):
        """Test multiple concurrent writes with exclusive locks."""
        tool = create_emotion_state_tool(dialogue_dir)

        def write_emotion_state(writer_id: int) -> tuple[int, str]:
            """Write emotion state and return writer ID and result."""
            result = tool.func(
                action="update",
                primary_emotion=f"emotion_{writer_id}",
                intensity=writer_id % 10 + 1,
            )
            return (writer_id, result)

        # Run 20 concurrent writes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_emotion_state, i) for i in range(20)]
            results = [future.result() for future in as_completed(futures)]

        # All writes should succeed
        assert len(results) == 20
        for writer_id, result in results:
            assert "Emotion state updated" in result

        # Verify all writes were recorded in history
        history_path = dialogue_dir / ".empathy" / "client" / "emotion-states" / "history.jsonl"
        assert history_path.exists()

        with history_path.open("r") as f:
            lines = f.readlines()

        # Should have exactly 20 lines
        assert len(lines) == 20

        # Verify all emotions are present
        emotions = set()
        for line in lines:
            data = json.loads(line.strip())
            emotions.add(data["primary_emotion"])

        assert len(emotions) == 20
        for i in range(20):
            assert f"emotion_{i}" in emotions

    def test_mixed_read_write_operations(self, dialogue_dir: Path):
        """Test mixed concurrent reads and writes."""
        tool = create_emotion_state_tool(dialogue_dir)

        def write_operation(op_id: int) -> tuple[str, int]:
            """Perform write operation."""
            tool.func(
                action="update",
                primary_emotion=f"emotion_{op_id}",
                intensity=5,
            )
            return ("write", op_id)

        def read_operation(op_id: int) -> tuple[str, int]:
            """Perform read operation."""
            tool.func(action="history")
            return ("read", op_id)

        # Run 10 writes and 10 reads concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(write_operation, i))
                futures.append(executor.submit(read_operation, i))

            results = [future.result() for future in as_completed(futures)]

        # All operations should succeed
        assert len(results) == 20
        write_count = sum(1 for op_type, _ in results if op_type == "write")
        read_count = sum(1 for op_type, _ in results if op_type == "read")
        assert write_count == 10
        assert read_count == 10

        # Verify all writes were recorded
        history_path = dialogue_dir / ".empathy" / "client" / "emotion-states" / "history.jsonl"
        with history_path.open("r") as f:
            lines = f.readlines()

        assert len(lines) == 10

    def test_file_integrity_under_concurrent_writes(self, dialogue_dir: Path):
        """Test that concurrent writes don't corrupt the file."""
        tool = create_emotion_state_tool(dialogue_dir)

        def write_with_delay(writer_id: int) -> int:
            """Write with a small delay to increase contention."""
            tool.func(
                action="update",
                primary_emotion=f"test_{writer_id}",
                intensity=writer_id % 10 + 1,
                thoughts=f"Thought from writer {writer_id}",
            )
            time.sleep(0.001)  # Small delay
            return writer_id

        # Run 50 concurrent writes with high contention
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(write_with_delay, i) for i in range(50)]
            results = [future.result() for future in as_completed(futures)]

        assert len(results) == 50

        # Verify file integrity - all lines should be valid JSON
        history_path = dialogue_dir / ".empathy" / "client" / "emotion-states" / "history.jsonl"
        with history_path.open("r") as f:
            lines = f.readlines()

        assert len(lines) == 50

        # Parse all lines - should not raise any exceptions
        parsed_count = 0
        for line in lines:
            stripped = line.strip()
            if stripped:
                data = json.loads(stripped)
                assert "primary_emotion" in data
                assert "intensity" in data
                assert "thoughts" in data
                parsed_count += 1

        assert parsed_count == 50
