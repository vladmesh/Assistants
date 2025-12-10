"""Background jobs for cron_service.

This package contains scheduled jobs that run periodically:
- memory_extraction: Extract facts from conversations using Batch API (Memory V2)

Note: Imports are lazy to avoid loading heavy dependencies (openai) at module level.
"""


def get_memory_extraction_job():
    """Get or create the singleton memory extraction job instance."""
    from .memory_extraction import get_memory_extraction_job as _get_job

    return _get_job()


async def run_memory_extraction():
    """Entry point for scheduler to run memory extraction."""
    from .memory_extraction import run_memory_extraction as _run

    return await _run()


__all__ = [
    "get_memory_extraction_job",
    "run_memory_extraction",
]
