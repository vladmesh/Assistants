#!/usr/bin/env python3
"""Script for running tests locally."""

import subprocess
import sys
from pathlib import Path


def get_services() -> list[str]:
    """Get list of all services."""
    return [
        "assistant_service",
        "rest_service",
        "google_calendar_service",
        "cron_service",
        "telegram_bot_service",
    ]


def run_tests(service: str | None = None) -> int:
    """Run tests locally.

    Args:
        service: Optional service name to test. If None, tests all services.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    services = [service] if service else get_services()

    for svc in services:
        service_path = Path(svc)
        if not service_path.exists():
            print(f"Service {svc} not found, skipping...")
            continue

        print(f"\nRunning tests for {svc} locally...")

        # Run pytest
        pytest_result = subprocess.run(
            ["poetry", "run", "pytest", str(service_path), "-v"],
            capture_output=True,
            text=True,
        )
        if pytest_result.returncode != 0:
            print("Tests failed:")
            print(pytest_result.stdout)
            return pytest_result.returncode

    return 0


def main() -> int:
    """Main entry point."""
    service = sys.argv[1] if len(sys.argv) > 1 else None
    return run_tests(service)


if __name__ == "__main__":
    sys.exit(main())
