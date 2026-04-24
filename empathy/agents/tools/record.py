"""Record tool - therapist clinical records (therapist only)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from empathy.storage.state import read_state


class RecordInput(BaseModel):
    """Input schema for record tool."""

    action: Literal["create", "read", "update", "list"] = Field(
        description="Action to perform on records"
    )
    record_type: Literal["assessment", "progress_note", "treatment_plan", "observation"] = Field(
        description="Type of clinical record"
    )
    content: str | None = Field(default=None, description="Record content for create/update")
    record_id: str | None = Field(default=None, description="Record ID for read/update")


def create_record_tool(dialogue_dir: Path) -> StructuredTool:
    """Create the record tool (therapist only).

    Args:
        dialogue_dir: Path to dialogue directory

    Returns:
        LangChain StructuredTool
    """

    def record_func(
        action: str,
        record_type: str,
        content: str | None = None,
        record_id: str | None = None,
    ) -> str:
        """Manage clinical records.

        Args:
            action: Action to perform (create/read/update/list)
            record_type: Type of record
            content: Record content
            record_id: Record ID

        Returns:
            Result message
        """
        records_dir = dialogue_dir / ".empathy" / "therapist" / "records" / f"{record_type}s"
        records_dir.mkdir(parents=True, exist_ok=True)

        state_path = dialogue_dir / ".empathy" / "state.json"

        if action == "create":
            if not content:
                return "Content is required for creating a record."

            # Get current turn number
            state = read_state(state_path)
            turn_number = state.get("turn_number", 0)

            record = {
                "id": str(uuid.uuid4()),
                "type": record_type,
                "timestamp": datetime.now(UTC).isoformat(),
                "turn_number": turn_number,
                "content": content,
                "tags": [],
                "related_turns": [],
            }

            path = records_dir / f"{record['timestamp']}_{record['id']}.json"
            path.write_text(json.dumps(record, indent=2, ensure_ascii=False))

            return f"Record created: {record['id']}"

        elif action == "read":
            if not record_id:
                return "Record ID is required for reading."

            path = next(records_dir.glob(f"*_{record_id}.json"), None)
            if not path:
                return f"Record not found: {record_id}"

            return path.read_text()

        elif action == "update":
            if not record_id:
                return "Record ID is required for updating."
            if not content:
                return "Content is required for updating a record."

            path = next(records_dir.glob(f"*_{record_id}.json"), None)
            if not path:
                return f"Record not found: {record_id}"

            record = json.loads(path.read_text())
            record["content"] = content
            record["updated_at"] = datetime.now(UTC).isoformat()

            path.write_text(json.dumps(record, indent=2, ensure_ascii=False))

            return f"Record updated: {record_id}"

        elif action == "list":
            records = []
            for path in sorted(records_dir.glob("*.json")):
                rec = json.loads(path.read_text())
                preview = rec["content"][:50] + "..." if len(rec["content"]) > 50 else rec["content"]
                records.append(f"[{rec['timestamp']}] {rec['type']}: {preview}")

            return "\n".join(records) if records else "No records found."

        else:
            return f"Unknown action: {action}"

    return StructuredTool.from_function(
        func=record_func,
        name="record",
        description="Manage clinical records (therapist only)",
        args_schema=RecordInput,
    )
