"""
Memory Layer for Multi-Agent Orchestra.

Hybrid architecture:
- JSONL as source of truth (auditable, versionable)
- mem0 as vector index (semantic search)
- Memory Broker for unified access
- Scoring Engine for importance/recall calculation
"""

from minions.memory.broker import MemoryBroker, get_broker
from minions.memory.embeddings import (
    EmbeddingProvider,
    get_embedding_provider,
    get_mem0_config,
)
from minions.memory.schema import (
    AgentType,
    MemoryEvent,
    MemoryScope,
    MemoryType,
)
from minions.memory.scoring import (
    ImportanceWeights,
    RecallWeights,
    ScoringContext,
    ScoringEngine,
    calculate_importance_score,
    calculate_recall_score,
    get_scoring_engine,
)

__all__ = [
    "AgentType",
    "EmbeddingProvider",
    "ImportanceWeights",
    "MemoryBroker",
    "MemoryEvent",
    "MemoryScope",
    "MemoryType",
    "RecallWeights",
    "ScoringContext",
    "ScoringEngine",
    "calculate_importance_score",
    "calculate_recall_score",
    "get_broker",
    "get_embedding_provider",
    "get_mem0_config",
    "get_scoring_engine",
]
