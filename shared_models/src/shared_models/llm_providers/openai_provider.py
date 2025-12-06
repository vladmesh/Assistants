import json
import logging
import tempfile
from pathlib import Path

from openai import AsyncOpenAI

from .base import BatchResult, BatchStatus, LLMProvider

logger = logging.getLogger(__name__)

OPENAI_BATCH_STATUS_MAP = {
    "validating": BatchStatus.PENDING,
    "in_progress": BatchStatus.IN_PROGRESS,
    "finalizing": BatchStatus.IN_PROGRESS,
    "completed": BatchStatus.COMPLETED,
    "failed": BatchStatus.FAILED,
    "expired": BatchStatus.EXPIRED,
    "cancelling": BatchStatus.FAILED,
    "cancelled": BatchStatus.FAILED,
}


class OpenAIProvider(LLMProvider):
    """OpenAI implementation with Batch API support."""

    def __init__(self, api_key: str | None = None):
        self.client = AsyncOpenAI(api_key=api_key)

    async def complete(self, prompt: str, model: str) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    async def submit_batch(
        self,
        requests: list[dict],
        model: str,
    ) -> str:
        """
        Submit batch request to OpenAI Batch API.

        Each request should have:
            - custom_id: Unique identifier
            - prompt: The prompt text
        """
        jsonl_lines = []
        for req in requests:
            batch_request = {
                "custom_id": req["custom_id"],
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [{"role": "user", "content": req["prompt"]}],
                },
            }
            jsonl_lines.append(json.dumps(batch_request))

        jsonl_content = "\n".join(jsonl_lines)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(jsonl_content)
            temp_path = Path(f.name)

        try:
            with open(temp_path, "rb") as f:
                batch_input_file = await self.client.files.create(
                    file=f, purpose="batch"
                )

            batch = await self.client.batches.create(
                input_file_id=batch_input_file.id,
                endpoint="/v1/chat/completions",
                completion_window="24h",
            )

            logger.info(f"Created OpenAI batch job: {batch.id}")
            return batch.id
        finally:
            temp_path.unlink(missing_ok=True)

    async def get_batch_status(self, batch_id: str) -> BatchStatus:
        batch = await self.client.batches.retrieve(batch_id)
        return OPENAI_BATCH_STATUS_MAP.get(batch.status, BatchStatus.PENDING)

    async def get_batch_results(self, batch_id: str) -> list[BatchResult]:
        batch = await self.client.batches.retrieve(batch_id)

        if batch.status != "completed" or not batch.output_file_id:
            logger.warning(
                f"Batch {batch_id} not completed or no output file. "
                f"Status: {batch.status}"
            )
            return []

        file_response = await self.client.files.content(batch.output_file_id)
        content = file_response.text

        results = []
        for line in content.strip().split("\n"):
            if not line:
                continue

            result_data = json.loads(line)
            custom_id = result_data.get("custom_id", "")

            if result_data.get("error"):
                results.append(
                    BatchResult(
                        custom_id=custom_id,
                        error=str(result_data["error"]),
                    )
                )
            else:
                response_body = result_data.get("response", {}).get("body", {})
                choices = response_body.get("choices", [])
                if choices:
                    content_text = choices[0].get("message", {}).get("content", "")
                    results.append(
                        BatchResult(
                            custom_id=custom_id,
                            content=content_text,
                        )
                    )
                else:
                    results.append(
                        BatchResult(
                            custom_id=custom_id,
                            error="No choices in response",
                        )
                    )

        return results

    async def generate_embedding(self, text: str, model: str) -> list[float]:
        response = await self.client.embeddings.create(
            input=text,
            model=model,
        )
        return response.data[0].embedding

    async def generate_embeddings(
        self, texts: list[str], model: str
    ) -> list[list[float]]:
        response = await self.client.embeddings.create(
            input=texts,
            model=model,
        )
        return [item.embedding for item in response.data]
