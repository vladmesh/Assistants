from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class BatchStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class BatchResult:
    custom_id: str
    content: str | None = None
    error: str | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers with batch support."""

    @abstractmethod
    async def complete(self, prompt: str, model: str) -> str:
        """Generate a single completion."""
        ...

    @abstractmethod
    async def submit_batch(
        self,
        requests: list[dict],
        model: str,
    ) -> str:
        """
        Submit a batch request.

        Args:
            requests: List of requests, each containing:
                - custom_id: Unique identifier for the request
                - prompt: The prompt to send
            model: Model to use for generation

        Returns:
            batch_id: Identifier for the batch job
        """
        ...

    @abstractmethod
    async def get_batch_status(self, batch_id: str) -> BatchStatus:
        """Get the current status of a batch job."""
        ...

    @abstractmethod
    async def get_batch_results(self, batch_id: str) -> list[BatchResult]:
        """
        Get results from a completed batch.

        Returns:
            List of BatchResult objects with content or error
        """
        ...

    @abstractmethod
    async def generate_embedding(self, text: str, model: str) -> list[float]:
        """Generate embedding vector for the given text."""
        ...

    @abstractmethod
    async def generate_embeddings(
        self, texts: list[str], model: str
    ) -> list[list[float]]:
        """Generate embedding vectors for multiple texts."""
        ...
