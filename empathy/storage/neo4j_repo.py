"""Neo4j-backed implementation of MemoryRepository."""

from __future__ import annotations

import logging
from datetime import datetime

from empathy.storage.memory_models import Memory, MemoryType
from empathy.storage.memory_repo import MemoryRepository

logger = logging.getLogger(__name__)


class Neo4jMemoryRepository(MemoryRepository):
    """Stores memories in a Neo4j graph database."""

    def __init__(self, uri: str, username: str, password: str) -> None:
        """Initialize Neo4j driver and ensure schema.

        Args:
            uri: Neo4j Bolt URI (e.g. bolt://localhost:7687)
            username: Neo4j username
            password: Neo4j password
        """
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create constraints and indexes. Ignores permission errors."""
        try:
            with self.driver.session() as session:
                session.run(
                    "CREATE CONSTRAINT memory_id_unique IF NOT EXISTS "
                    "FOR (m:Memory) REQUIRE m.id IS UNIQUE"
                )
                session.run(
                    "CREATE FULLTEXT INDEX memory_content_index IF NOT EXISTS "
                    "FOR (m:Memory) ON EACH [m.content]"
                )
        except Exception:
            logger.warning(
                "Could not create Neo4j schema constraints/indexes. "
                "Ensure they exist manually or the user has schema privileges."
            )

    def store(self, user_id: str, memory: Memory) -> str:
        with self.driver.session() as session:
            session.run(
                """
                MERGE (u:User {user_id: $user_id})
                CREATE (m:Memory {
                    id: $id,
                    type: $type,
                    content: $content,
                    importance: $importance,
                    created_at: datetime($created_at),
                    updated_at: datetime($updated_at)
                })
                CREATE (u)-[:HAS_MEMORY]->(m)
                """,
                user_id=user_id,
                id=memory.id,
                type=memory.type,
                content=memory.content,
                importance=memory.importance,
                created_at=memory.created_at.isoformat(),
                updated_at=(memory.updated_at or memory.created_at).isoformat(),
            )
        return memory.id

    def retrieve(self, user_id: str, memory_id: str) -> Memory | None:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory {id: $id})
                RETURN m.id AS id, m.type AS type, m.content AS content,
                       m.importance AS importance, m.created_at AS created_at,
                       m.updated_at AS updated_at
                """,
                user_id=user_id,
                id=memory_id,
            )
            record = result.single()
            if record is None:
                return None
            return self._record_to_memory(record)

    def search(
        self,
        user_id: str,
        query: str,
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        with self.driver.session() as session:
            if memory_type:
                result = session.run(
                    """
                    CALL db.index.fulltext.queryNodes('memory_content_index', $query)
                    YIELD node, score
                    MATCH (:User {user_id: $user_id})-[:HAS_MEMORY]->(node)
                    WHERE node.type = $memory_type
                    RETURN node.id AS id, node.type AS type, node.content AS content,
                           node.importance AS importance, node.created_at AS created_at,
                           node.updated_at AS updated_at
                    ORDER BY score DESC, node.importance DESC
                    LIMIT $limit
                    """,
                    user_id=user_id,
                    query=query,
                    memory_type=memory_type,
                    limit=limit,
                )
            else:
                result = session.run(
                    """
                    CALL db.index.fulltext.queryNodes('memory_content_index', $query)
                    YIELD node, score
                    MATCH (:User {user_id: $user_id})-[:HAS_MEMORY]->(node)
                    RETURN node.id AS id, node.type AS type, node.content AS content,
                           node.importance AS importance, node.created_at AS created_at,
                           node.updated_at AS updated_at
                    ORDER BY score DESC, node.importance DESC
                    LIMIT $limit
                    """,
                    user_id=user_id,
                    query=query,
                    limit=limit,
                )
            return [self._record_to_memory(r) for r in result]

    def list_by_type(self, user_id: str, memory_type: MemoryType) -> list[Memory]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory {type: $type})
                RETURN m.id AS id, m.type AS type, m.content AS content,
                       m.importance AS importance, m.created_at AS created_at,
                       m.updated_at AS updated_at
                ORDER BY m.importance DESC, m.created_at DESC
                """,
                user_id=user_id,
                type=memory_type,
            )
            return [self._record_to_memory(r) for r in result]

    def update(self, user_id: str, memory_id: str, content: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory {id: $id})
                SET m.content = $content, m.updated_at = datetime()
                RETURN count(m) AS updated
                """,
                user_id=user_id,
                id=memory_id,
                content=content,
            )
            record = result.single()
            return record is not None and record["updated"] > 0

    def delete(self, user_id: str, memory_id: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory {id: $id})
                DETACH DELETE m
                RETURN count(m) AS deleted
                """,
                user_id=user_id,
                id=memory_id,
            )
            record = result.single()
            return record is not None and record["deleted"] > 0

    def list_all(self, user_id: str) -> list[Memory]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)
                RETURN m.id AS id, m.type AS type, m.content AS content,
                       m.importance AS importance, m.created_at AS created_at,
                       m.updated_at AS updated_at
                ORDER BY m.importance DESC, m.created_at DESC
                """,
                user_id=user_id,
            )
            return [self._record_to_memory(r) for r in result]

    @staticmethod
    def _record_to_memory(record) -> Memory:
        created = record["created_at"]
        updated = record["updated_at"]
        return Memory(
            id=record["id"],
            type=record["type"],
            content=record["content"],
            importance=record["importance"],
            created_at=(
                created if isinstance(created, datetime) else datetime.fromisoformat(str(created))
            ),
            updated_at=(
                updated
                if updated is None or isinstance(updated, datetime)
                else datetime.fromisoformat(str(updated))
            ),
        )
