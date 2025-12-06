"""Memory V2 Batch Extraction Job.

This job periodically extracts facts from user conversations using LLM Batch API.
It runs in the background to save costs (Batch API is ~50% cheaper than real-time).

Architecture:
------------
1. Fetch recent conversations from REST service (messages since last extraction)
2. For each user/assistant pair, build a batch request with extraction prompt
3. Submit batch to LLM provider (OpenAI/Google/Anthropic via LLMProvider abstraction)
4. Poll for batch completion (or use webhooks if available)
5. Process results: deduplicate facts using semantic similarity
6. Save new/updated memories to RAG service

Configuration (from GlobalSettings):
-----------------------------------
- memory_extraction_enabled: bool - Whether extraction is enabled
- memory_extraction_interval_hours: int - How often to run (default: 24h)
- memory_extraction_model: str - LLM model for extraction (e.g., "gpt-4o-mini")
- memory_extraction_provider: str - Provider: "openai", "google", "anthropic"
- memory_dedup_threshold: float - Similarity threshold for deduplication (0.85)
- memory_update_threshold: float - Threshold for updating existing fact (0.95)

Batch Job Tracking:
------------------
Batch jobs are tracked in the database (BatchJob model in rest_service) to:
- Resume processing after service restart
- Track job status: pending, completed, failed
- Store batch_id from provider for result retrieval

Usage:
-----
This job is registered in the scheduler and runs automatically based on
the configured interval. Manual trigger is also possible via admin API.

Example flow:
    1. Job starts, fetches GlobalSettings
    2. If extraction disabled, exits early
    3. Fetches conversations since last run
    4. Groups by user, builds extraction prompts
    5. Submits batch request to configured provider
    6. Saves BatchJob record with batch_id
    7. Later run checks pending batches, processes completed ones
    8. Extracted facts are deduplicated and saved to Memory V2

Note: This is a stub implementation. Full implementation requires:
- BatchJob model in rest_service
- REST endpoints for conversations retrieval
- Integration with shared_models LLMProvider
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# Prompt template for fact extraction
FACT_EXTRACTION_PROMPT = """
Проанализируй диалог и извлеки важные факты о пользователе.

## Типы фактов:
- user_fact: личная информация (имя, возраст, профессия, место жительства)
- preference: предпочтения (любит/не любит, интересы, хобби)
- event: важные события (день рождения, встречи, планы)
- conversation_insight: инсайты из разговора (контекст, темы обсуждений)

## Уже известные факты (НЕ ПОВТОРЯЙ):
{existing_facts}

## Диалог:
{conversation}

## Инструкции:
1. Извлекай только НОВУЮ информацию, которой нет в известных фактах
2. Формулируй кратко и конкретно (1-2 предложения)
3. Указывай тип факта и важность (1-10, где 10 = критически важно)
4. Не дублируй и не перефразируй известные факты
5. Если нет новой информации, верни пустой список

Ответ строго в формате JSON (без markdown):
[
  {{"text": "...", "memory_type": "...", "importance": N}},
  ...
]
"""


@dataclass
class ExtractionResult:
    """Result of a single fact extraction."""

    text: str
    memory_type: str
    importance: int
    user_id: int
    assistant_id: str | None = None


class MemoryExtractionJob:
    """
    Periodically extracts facts from conversations using Batch API.

    This job is designed to run in the background with minimal impact on
    real-time operations. It uses provider Batch APIs which are typically
    50% cheaper than real-time API calls.

    Attributes:
        rest_client: Client for REST service API
        rag_client: Client for RAG service API (Memory V2)
        settings: Cached GlobalSettings
        llm_provider: Configured LLM provider for batch operations
    """

    def __init__(self):
        """Initialize the job. Clients are created lazily on first run."""
        self._rest_client = None
        self._rag_client = None
        self._settings = None
        self._llm_provider = None
        self._last_run: datetime | None = None

    async def run(self) -> dict[str, Any]:
        """
        Main entry point for the extraction job.

        Returns:
            Dict with job execution statistics:
            - started_at: Job start timestamp
            - conversations_processed: Number of conversations analyzed
            - batches_submitted: Number of batch requests submitted
            - facts_extracted: Number of new facts found
            - facts_deduplicated: Number of duplicate facts filtered
            - errors: List of any errors encountered
        """
        logger.info("MemoryExtractionJob: Starting extraction run...")

        stats = {
            "started_at": datetime.utcnow().isoformat(),
            "conversations_processed": 0,
            "batches_submitted": 0,
            "facts_extracted": 0,
            "facts_deduplicated": 0,
            "errors": [],
        }

        try:
            # Step 1: Load settings and check if enabled
            settings = await self._get_settings()
            if not settings.get("memory_extraction_enabled", True):
                logger.info("MemoryExtractionJob: Extraction is disabled in settings")
                stats["status"] = "disabled"
                return stats

            # Step 2: Check pending batches from previous runs
            pending_results = await self._process_pending_batches()
            stats["facts_extracted"] += pending_results.get("facts_extracted", 0)
            stats["facts_deduplicated"] += pending_results.get("facts_deduplicated", 0)

            # Step 3: Fetch new conversations since last run
            conversations = await self._fetch_recent_conversations()
            stats["conversations_processed"] = len(conversations)

            if not conversations:
                logger.info("MemoryExtractionJob: No new conversations to process")
                stats["status"] = "no_new_data"
                return stats

            # Step 4: Build and submit batch requests
            batches = await self._submit_extraction_batches(conversations)
            stats["batches_submitted"] = len(batches)

            stats["status"] = "submitted"
            logger.info(
                "MemoryExtractionJob: Submitted %d batches for %d conversations",
                len(batches),
                len(conversations),
            )

        except Exception as e:
            logger.error("MemoryExtractionJob: Error during run: %s", e, exc_info=True)
            stats["errors"].append(str(e))
            stats["status"] = "error"

        stats["finished_at"] = datetime.utcnow().isoformat()
        self._last_run = datetime.utcnow()
        return stats

    async def _get_settings(self) -> dict[str, Any]:
        """Fetch GlobalSettings from REST service."""
        # TODO: Implement actual settings fetch
        # For now, return defaults matching GlobalSettings model
        logger.debug("MemoryExtractionJob: Fetching settings (stub)")
        return {
            "memory_extraction_enabled": True,
            "memory_extraction_interval_hours": 24,
            "memory_extraction_model": "gpt-4o-mini",
            "memory_extraction_provider": "openai",
            "memory_dedup_threshold": 0.85,
            "memory_update_threshold": 0.95,
        }

    async def _fetch_recent_conversations(self) -> list[dict]:
        """
        Fetch conversations since last extraction run.

        Returns:
            List of conversation dicts with:
            - user_id: User identifier
            - assistant_id: Assistant identifier
            - messages: List of message dicts
        """
        # TODO: Implement actual conversation fetch from REST service
        # Need endpoint: GET /api/conversations?since={last_run_timestamp}
        logger.debug("MemoryExtractionJob: Fetching conversations (stub)")
        return []

    async def _get_existing_facts(self, user_id: int) -> list[dict]:
        """
        Get existing facts for a user to avoid duplicates.

        Args:
            user_id: User to get facts for

        Returns:
            List of existing memory dicts
        """
        # TODO: Implement via RAG service client
        logger.debug("MemoryExtractionJob: Fetching existing facts (stub)")
        return []

    async def _submit_extraction_batches(self, conversations: list[dict]) -> list[str]:
        """
        Build and submit batch extraction requests.

        Args:
            conversations: List of conversation dicts to process

        Returns:
            List of batch_ids for tracking
        """
        # TODO: Implement batch submission
        # 1. Group conversations by user
        # 2. For each user, get existing facts
        # 3. Build extraction prompt with FACT_EXTRACTION_PROMPT
        # 4. Submit to LLMProvider.submit_batch()
        # 5. Save BatchJob record in database
        logger.debug("MemoryExtractionJob: Submitting batches (stub)")
        return []

    async def _process_pending_batches(self) -> dict[str, int]:
        """
        Check and process any pending batch jobs from previous runs.

        Returns:
            Dict with processing statistics
        """
        # TODO: Implement batch result processing
        # 1. Fetch pending BatchJob records from database
        # 2. Check status with LLMProvider.get_batch_status()
        # 3. For completed batches, get results
        # 4. Deduplicate facts using semantic similarity
        # 5. Save to Memory V2 via RAG service
        # 6. Update BatchJob status
        logger.debug("MemoryExtractionJob: Processing pending batches (stub)")
        return {"facts_extracted": 0, "facts_deduplicated": 0}

    async def _deduplicate_facts(
        self,
        new_facts: list[ExtractionResult],
        user_id: int,
        dedup_threshold: float = 0.85,
        update_threshold: float = 0.95,
    ) -> list[ExtractionResult]:
        """
        Filter and deduplicate extracted facts using semantic similarity.

        Logic:
        - similarity > update_threshold: Update existing fact text
        - dedup_threshold < similarity <= update_threshold: Update existing
        - similarity <= dedup_threshold: Create new fact

        Args:
            new_facts: Newly extracted facts
            user_id: User ID for lookup
            dedup_threshold: Similarity threshold for considering duplicate
            update_threshold: Threshold for simple update vs new fact

        Returns:
            List of unique facts to save
        """
        # TODO: Implement semantic deduplication
        # 1. For each new fact, generate embedding
        # 2. Search existing facts with embedding
        # 3. If high similarity found, update or skip
        # 4. Otherwise, add to unique list
        logger.debug("MemoryExtractionJob: Deduplicating facts (stub)")
        return new_facts

    async def _save_memories(self, facts: list[ExtractionResult]) -> int:
        """
        Save extracted facts to Memory V2 via RAG service.

        Args:
            facts: List of facts to save

        Returns:
            Number of successfully saved facts
        """
        # TODO: Implement via RAG service client
        logger.debug("MemoryExtractionJob: Saving memories (stub)")
        return 0


# Singleton instance for scheduler registration
_job_instance: MemoryExtractionJob | None = None


def get_memory_extraction_job() -> MemoryExtractionJob:
    """Get or create the singleton job instance."""
    global _job_instance
    if _job_instance is None:
        _job_instance = MemoryExtractionJob()
    return _job_instance


async def run_memory_extraction() -> dict[str, Any]:
    """
    Entry point for scheduler to run memory extraction.

    This function is called by APScheduler at the configured interval.

    Returns:
        Job execution statistics
    """
    job = get_memory_extraction_job()
    return await job.run()
