#!/usr/bin/env python3
"""Script for running code linters locally."""

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


def run_linters(service: str | None = None) -> int:
    """Run linters on Python files locally.

    Args:
        service: Optional service name to lint. If None, lints all services.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    services = [service] if service else get_services()

    for svc in services:
        service_path = Path(svc)
        if not service_path.exists():
            print(f"Service {svc} not found, skipping...")
            continue

        print(f"\nRunning linters on {svc} locally...")

        # Run flake8
        flake8_result = subprocess.run(
            ["poetry", "run", "flake8", str(service_path)],
            capture_output=True,
            text=True,
        )
        if flake8_result.returncode != 0:
            print("flake8 found issues:")
            print(flake8_result.stdout)
            return flake8_result.returncode

        # Run mypy
        mypy_result = subprocess.run(
            ["poetry", "run", "mypy", str(service_path)],
            capture_output=True,
            text=True,
        )
        if mypy_result.returncode != 0:
            print("mypy found type issues:")
            print(mypy_result.stdout)
            return mypy_result.returncode

        # Run pylint
        pylint_result = subprocess.run(
            ["poetry", "run", "pylint", str(service_path)],
            capture_output=True,
            text=True,
        )
        if pylint_result.returncode != 0:
            print("pylint found issues:")
            print(pylint_result.stdout)
            return pylint_result.returncode

    return 0


def main() -> int:
    """Main entry point."""
    service = sys.argv[1] if len(sys.argv) > 1 else None
    return run_linters(service)


if __name__ == "__main__":
    sys.exit(main())
