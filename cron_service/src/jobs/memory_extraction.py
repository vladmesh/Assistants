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
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from rest_client import (
    create_batch_job,
    fetch_conversations,
    fetch_global_settings,
    fetch_pending_batch_jobs,
    update_batch_job_status,
)

if TYPE_CHECKING:
    from shared_models.llm_providers.base import LLMProvider

logger = logging.getLogger(__name__)

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://rag_service:8000")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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
    """

    def __init__(self):
        """Initialize the job. Clients are created lazily on first run."""
        self._settings: dict[str, Any] | None = None
        self._llm_provider: LLMProvider | None = None
        self._last_run: datetime | None = None
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close resources."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    def _get_llm_provider(self, provider_name: str) -> LLMProvider:
        """Get or create LLM provider instance."""
        if self._llm_provider is None:
            # Lazy import to avoid loading openai at module level
            from shared_models.llm_providers import get_llm_provider

            self._llm_provider = get_llm_provider(
                provider_name,
                api_key=OPENAI_API_KEY,
            )
        return self._llm_provider

    async def run(self) -> dict[str, Any]:
        """
        Main entry point for the extraction job.

        Returns:
            Dict with job execution statistics.
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
            pending_results = await self._process_pending_batches(settings)
            stats["facts_extracted"] += pending_results.get("facts_extracted", 0)
            stats["facts_deduplicated"] += pending_results.get("facts_deduplicated", 0)

            # Step 3: Fetch new conversations since last run
            conversations = await self._fetch_recent_conversations(settings)
            stats["conversations_processed"] = len(conversations)

            if not conversations:
                logger.info("MemoryExtractionJob: No new conversations to process")
                stats["status"] = "no_new_data"
                return stats

            # Step 4: Build and submit batch requests
            batches = await self._submit_extraction_batches(conversations, settings)
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
        settings = fetch_global_settings()
        if settings is None:
            logger.warning("Failed to fetch settings, using defaults")
            return {
                "memory_extraction_enabled": True,
                "memory_extraction_interval_hours": 24,
                "memory_extraction_model": "gpt-4o-mini",
                "memory_extraction_provider": "openai",
                "memory_dedup_threshold": 0.85,
                "memory_update_threshold": 0.95,
                "embedding_model": "text-embedding-3-small",
            }
        self._settings = settings
        return settings

    async def _fetch_recent_conversations(self, settings: dict[str, Any]) -> list[dict]:
        """Fetch conversations since last extraction run."""
        interval_hours = settings.get("memory_extraction_interval_hours", 24)

        # Calculate since timestamp
        if self._last_run:
            since = self._last_run
        else:
            since = datetime.utcnow() - timedelta(hours=interval_hours)

        conversations = fetch_conversations(
            since=since,
            min_messages=2,
            limit=50,
        )

        logger.info(
            "Fetched %d conversations since %s",
            len(conversations),
            since.isoformat(),
        )
        return conversations

    async def _get_existing_facts(self, user_id: int) -> list[dict]:
        """Get existing facts for a user to avoid duplicates."""
        try:
            client = await self._get_http_client()
            response = await client.post(
                f"{RAG_SERVICE_URL}/api/memory/search",
                json={
                    "query": "все факты о пользователе",
                    "user_id": user_id,
                    "limit": 50,
                    "threshold": 0.0,  # Get all facts
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Error fetching existing facts for user %d: %s", user_id, e)
            return []

    def _format_conversation(self, conversation: dict) -> str:
        """Format conversation messages for the prompt."""
        messages = conversation.get("messages", [])
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _format_existing_facts(self, facts: list[dict]) -> str:
        """Format existing facts for the prompt."""
        if not facts:
            return "Нет известных фактов."
        lines = []
        for fact in facts:
            text = fact.get("text", "")
            memory_type = fact.get("memory_type", "")
            lines.append(f"- [{memory_type}] {text}")
        return "\n".join(lines)

    async def _submit_extraction_batches(
        self,
        conversations: list[dict],
        settings: dict[str, Any],
    ) -> list[str]:
        """Build and submit batch extraction requests."""
        provider_name = settings.get("memory_extraction_provider", "openai")
        model = settings.get("memory_extraction_model", "gpt-4o-mini")

        provider = self._get_llm_provider(provider_name)

        batch_ids = []

        # Group conversations by user_id
        by_user: dict[int, list[dict]] = {}
        for conv in conversations:
            user_id = conv.get("user_id")
            if user_id:
                if user_id not in by_user:
                    by_user[user_id] = []
                by_user[user_id].append(conv)

        for user_id, user_conversations in by_user.items():
            try:
                # Get existing facts for this user
                existing_facts = await self._get_existing_facts(user_id)
                existing_facts_str = self._format_existing_facts(existing_facts)

                # Build batch requests for each conversation
                batch_requests = []
                for conv in user_conversations:
                    conversation_str = self._format_conversation(conv)
                    prompt = FACT_EXTRACTION_PROMPT.format(
                        existing_facts=existing_facts_str,
                        conversation=conversation_str,
                    )
                    assistant_id = conv.get("assistant_id", "unknown")
                    custom_id = (
                        f"user_{user_id}_conv_{assistant_id}_{uuid.uuid4().hex[:8]}"
                    )
                    batch_requests.append(
                        {
                            "custom_id": custom_id,
                            "prompt": prompt,
                        }
                    )

                if not batch_requests:
                    continue

                # Submit batch to LLM provider
                batch_id = await provider.submit_batch(batch_requests, model)
                batch_ids.append(batch_id)

                # Record batch job in database
                create_batch_job(
                    batch_id=batch_id,
                    user_id=user_id,
                    provider=provider_name,
                    model=model,
                    messages_processed=sum(
                        len(c.get("messages", [])) for c in user_conversations
                    ),
                )

                logger.info(
                    "Submitted batch %s for user %d (%d conversations)",
                    batch_id,
                    user_id,
                    len(user_conversations),
                )

            except Exception as e:
                logger.error(
                    "Error submitting batch for user %d: %s", user_id, e, exc_info=True
                )

        return batch_ids

    async def _process_pending_batches(
        self, settings: dict[str, Any]
    ) -> dict[str, int]:
        """Check and process any pending batch jobs from previous runs."""
        # Lazy import to avoid loading openai at module level
        from shared_models.llm_providers.base import BatchStatus

        stats = {"facts_extracted": 0, "facts_deduplicated": 0}

        pending_jobs = fetch_pending_batch_jobs()
        if not pending_jobs:
            logger.info("No pending batch jobs to process")
            return stats

        provider_name = settings.get("memory_extraction_provider", "openai")
        provider = self._get_llm_provider(provider_name)

        for job in pending_jobs:
            try:
                batch_id = job.get("batch_id")
                job_id = job.get("id")
                user_id = job.get("user_id")

                if not batch_id or not job_id:
                    continue

                # Check batch status
                status = await provider.get_batch_status(batch_id)
                logger.info("Batch %s status: %s", batch_id, status)

                if status == BatchStatus.COMPLETED:
                    # Get results
                    results = await provider.get_batch_results(batch_id)

                    # Parse and save facts
                    facts_count = 0
                    for result in results:
                        if result.error:
                            logger.warning(
                                "Batch result error for %s: %s",
                                result.custom_id,
                                result.error,
                            )
                            continue

                        if result.content:
                            parsed_facts = self._parse_extraction_result(
                                result.content, user_id
                            )
                            for fact in parsed_facts:
                                saved = await self._save_memory(fact, settings)
                                if saved:
                                    facts_count += 1

                    stats["facts_extracted"] += facts_count

                    # Update job status
                    update_batch_job_status(
                        job_id=job_id,
                        status="completed",
                        facts_extracted=facts_count,
                    )

                elif status == BatchStatus.FAILED:
                    update_batch_job_status(
                        job_id=job_id,
                        status="failed",
                        error_message="Batch job failed at provider",
                    )

                elif status == BatchStatus.EXPIRED:
                    update_batch_job_status(
                        job_id=job_id,
                        status="failed",
                        error_message="Batch job expired",
                    )

            except Exception as e:
                logger.error(
                    "Error processing batch job %s: %s",
                    job.get("id"),
                    e,
                    exc_info=True,
                )

        return stats

    def _parse_extraction_result(
        self, content: str, user_id: int
    ) -> list[ExtractionResult]:
        """Parse LLM extraction result JSON into ExtractionResult objects."""
        try:
            # Try to parse JSON
            facts = json.loads(content.strip())
            if not isinstance(facts, list):
                logger.warning("Extraction result is not a list: %s", content[:100])
                return []

            results = []
            for fact in facts:
                if not isinstance(fact, dict):
                    continue

                text = fact.get("text", "").strip()
                memory_type = fact.get("memory_type", "user_fact")
                importance = fact.get("importance", 1)

                if not text:
                    continue

                # Validate memory_type
                valid_types = [
                    "user_fact",
                    "preference",
                    "event",
                    "conversation_insight",
                ]
                if memory_type not in valid_types:
                    memory_type = "user_fact"

                # Validate importance
                try:
                    importance = int(importance)
                    importance = max(1, min(10, importance))
                except (ValueError, TypeError):
                    importance = 1

                results.append(
                    ExtractionResult(
                        text=text,
                        memory_type=memory_type,
                        importance=importance,
                        user_id=user_id,
                    )
                )

            return results

        except json.JSONDecodeError:
            logger.warning(
                "Failed to parse extraction result as JSON: %s", content[:200]
            )
            return []

    async def _save_memory(
        self, fact: ExtractionResult, settings: dict[str, Any]
    ) -> bool:
        """Save a fact to Memory V2 via RAG service."""
        try:
            client = await self._get_http_client()

            # First check for similar existing memories (deduplication)
            dedup_threshold = settings.get("memory_dedup_threshold", 0.85)

            search_response = await client.post(
                f"{RAG_SERVICE_URL}/api/memory/search",
                json={
                    "query": fact.text,
                    "user_id": fact.user_id,
                    "limit": 1,
                    "threshold": dedup_threshold,
                },
            )

            if search_response.status_code == 200:
                similar = search_response.json()
                if similar:
                    # Found similar fact, skip
                    logger.debug(
                        "Skipping duplicate fact for user %d: %s",
                        fact.user_id,
                        fact.text[:50],
                    )
                    return False

            # Create new memory
            payload = {
                "user_id": fact.user_id,
                "text": fact.text,
                "memory_type": fact.memory_type,
                "importance": fact.importance,
            }
            if fact.assistant_id:
                payload["assistant_id"] = fact.assistant_id

            response = await client.post(
                f"{RAG_SERVICE_URL}/api/memory/",
                json=payload,
            )
            response.raise_for_status()

            logger.info(
                "Saved memory for user %d: %s",
                fact.user_id,
                fact.text[:50],
            )
            return True

        except Exception as e:
            logger.error(
                "Error saving memory for user %d: %s",
                fact.user_id,
                e,
            )
            return False


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
