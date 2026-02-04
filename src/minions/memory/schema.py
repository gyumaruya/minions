"""
Memory Schema - Unified schema for multi-agent memory system.

Defines the standard format for memories across all agents.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MemoryScope(str, Enum):
    """Memory visibility scope."""

    SESSION = "session"  # Current session only (temporary)
    PROJECT = "project"  # Project-specific, persistent
    USER = "user"  # User-wide, persistent
    AGENT = "agent"  # Specific agent only
    PUBLIC = "public"  # Shared across all agents


class MemoryType(str, Enum):
    """Type of memory event."""

    OBSERVATION = "observation"  # Factual observation
    DECISION = "decision"  # Design/implementation decision
    PLAN = "plan"  # Future plan or intent
    ARTIFACT = "artifact"  # Code, file, or output reference
    PREFERENCE = "preference"  # User preference
    WORKFLOW = "workflow"  # Workflow pattern
    ERROR = "error"  # Error pattern and solution
    RESEARCH = "research"  # Research finding


class AgentType(str, Enum):
    """Agent identifiers."""

    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"
    COPILOT = "copilot"
    SYSTEM = "system"  # For system-generated memories


@dataclass
class MemoryEvent:
    """
    Unified memory event schema.

    All memories across all agents conform to this schema.
    """

    # Required fields
    content: str
    memory_type: MemoryType
    scope: MemoryScope
    source_agent: AgentType

    # Auto-generated fields
    id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Optional fields
    context: str = ""
    confidence: float = 1.0  # 0.0 to 1.0
    ttl_days: int | None = None  # Time to live, None = permanent
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Embedding (populated by mem0)
    embedding: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "scope": self.scope.value,
            "source_agent": self.source_agent.value,
            "context": self.context,
            "confidence": self.confidence,
            "ttl_days": self.ttl_days,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEvent":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            scope=MemoryScope(data["scope"]),
            source_agent=AgentType(data["source_agent"]),
            context=data.get("context", ""),
            confidence=data.get("confidence", 1.0),
            ttl_days=data.get("ttl_days"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
        )


# Sensitive patterns to redact
SENSITIVE_PATTERNS = [
    r"sk-[a-zA-Z0-9_-]{20,}",  # OpenAI API key (various formats)
    r"sk-proj-[a-zA-Z0-9_-]+",  # OpenAI project API key
    r"sk-ant-[a-zA-Z0-9\-]{20,}",  # Anthropic API key
    r"AIza[a-zA-Z0-9_-]{35}",  # Google API key
    r"ghp_[a-zA-Z0-9]{36}",  # GitHub token
    r"gho_[a-zA-Z0-9]{36}",  # GitHub OAuth token
    r"password\s*[:=]\s*\S+",  # Password patterns
    r"secret\s*[:=]\s*\S+",  # Secret patterns
]
