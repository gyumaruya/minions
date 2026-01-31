"""
Embedding Provider Abstraction Layer.

Supports multiple embedding providers with fallback:
- OpenAI (text-embedding-3-small)
- HuggingFace (local, no API needed)
- Ollama (local)
"""

import os
from abc import ABC, abstractmethod
from typing import Any


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return embedding dimension."""
        pass


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self._dimension = 1536 if "small" in model else 3072

        try:
            from openai import OpenAI
            self.client = OpenAI()
        except ImportError as e:
            raise ImportError("openai package required: uv add openai") from e

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [d.embedding for d in response.data]

    @property
    def dimension(self) -> int:
        return self._dimension


class HuggingFaceEmbedding(EmbeddingProvider):
    """HuggingFace local embedding provider (no API needed)."""

    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model

        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model)
            self._dimension = self.model.get_sentence_embedding_dimension()
        except ImportError as e:
            raise ImportError(
                "sentence-transformers required: uv add sentence-transformers"
            ) from e

    def embed(self, text: str) -> list[float]:
        embedding = self.model.encode(text)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts)
        return [e.tolist() for e in embeddings]

    @property
    def dimension(self) -> int:
        return self._dimension


class OllamaEmbedding(EmbeddingProvider):
    """Ollama local embedding provider."""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        host: str = "http://localhost:11434",
    ):
        self.model = model
        self.host = host
        self._dimension = 768  # Default for nomic-embed-text

        try:
            import httpx
            self.client = httpx.Client(base_url=host, timeout=30.0)
        except ImportError as e:
            raise ImportError("httpx required: uv add httpx") from e

    def embed(self, text: str) -> list[float]:
        response = self.client.post(
            "/api/embeddings",
            json={"model": self.model, "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    @property
    def dimension(self) -> int:
        return self._dimension


def get_embedding_provider(
    provider: str = "auto",
    **kwargs: Any,
) -> EmbeddingProvider:
    """
    Get embedding provider by name or auto-detect.

    Args:
        provider: Provider name (openai, huggingface, ollama, auto)
        **kwargs: Provider-specific arguments

    Returns:
        EmbeddingProvider instance
    """
    if provider == "auto":
        # Try providers in order of preference
        if os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        else:
            # Fall back to HuggingFace (local, no API needed)
            provider = "huggingface"

    if provider == "openai":
        return OpenAIEmbedding(**kwargs)
    elif provider == "huggingface":
        return HuggingFaceEmbedding(**kwargs)
    elif provider == "ollama":
        return OllamaEmbedding(**kwargs)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


def get_mem0_config(
    embedding_provider: str = "auto",
    llm_provider: str = "auto",
    vector_store_path: str | None = None,
) -> dict[str, Any]:
    """
    Generate mem0 configuration based on available providers.

    Args:
        embedding_provider: Embedding provider (openai, huggingface, ollama, auto)
        llm_provider: LLM provider (openai, anthropic, auto)
        vector_store_path: Path for persistent vector store

    Returns:
        mem0 configuration dictionary
    """
    config: dict[str, Any] = {}

    # Auto-detect LLM provider
    if llm_provider == "auto":
        if os.environ.get("ANTHROPIC_API_KEY"):
            llm_provider = "anthropic"
        elif os.environ.get("OPENAI_API_KEY"):
            llm_provider = "openai"
        else:
            llm_provider = "openai"  # Will fail if no key

    # LLM config
    if llm_provider == "anthropic":
        config["llm"] = {
            "provider": "anthropic",
            "config": {
                "model": "claude-sonnet-4-20250514",
                "temperature": 0.1,
            },
        }
    elif llm_provider == "openai":
        config["llm"] = {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
                "temperature": 0.1,
            },
        }

    # Auto-detect embedding provider
    if embedding_provider == "auto":
        if os.environ.get("OPENAI_API_KEY"):
            embedding_provider = "openai"
        else:
            embedding_provider = "huggingface"

    # Embedder config
    if embedding_provider == "openai":
        config["embedder"] = {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
            },
        }
    elif embedding_provider == "huggingface":
        config["embedder"] = {
            "provider": "huggingface",
            "config": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
            },
        }
    elif embedding_provider == "ollama":
        config["embedder"] = {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text",
            },
        }

    # Vector store config
    if vector_store_path:
        config["vector_store"] = {
            "provider": "qdrant",
            "config": {
                "collection_name": "minions_memory",
                "path": vector_store_path,
            },
        }

    return config
