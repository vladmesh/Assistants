#!/usr/bin/env python3
"""Script for running code formatters locally."""

import subprocess
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


def run_formatters(service: str | None = None) -> int:
    """Run formatters on Python files locally.

    Args:
        service: Optional service name to format. If None, formats all services.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    services = [service] if service else get_services()

    for svc in services:
        service_path = Path(svc)
        if not service_path.exists():
            print(f"Service {svc} not found, skipping...")
            continue

        print(f"\nRunning formatters on {svc} locally...")

        # Run black
        black_result = subprocess.run(
            ["poetry", "run", "black", "--check", str(service_path)],
            capture_output=True,
            text=True,
        )
        if black_result.returncode != 0:
            print("Black found formatting issues:")
            print(black_result.stdout)
            return black_result.returncode

        # Run isort
        isort_result = subprocess.run(
            ["poetry", "run", "isort", "--check-only", str(service_path)],
            capture_output=True,
            text=True,
        )
        if isort_result.returncode != 0:
            print("isort found import sorting issues:")
            print(isort_result.stdout)
            return isort_result.returncode

    return 0


def main():
    """Format all Python files in the project."""
    import subprocess
    import sys

    def run_tool(cmd):
        try:
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    isort_success = run_tool(["isort", "."])
    black_success = run_tool(["black", "."])

    if not (isort_success and black_success):
        sys.exit(1)


if __name__ == "__main__":
    main()
