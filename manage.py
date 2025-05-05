#!/usr/bin/env python3
import argparse
import subprocess
import sys
from typing import Optional


def run_command(command: str) -> int:
    """Run a command and return its result."""
    try:
        result = subprocess.run(command, shell=True, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        return e.returncode


def get_service_container(service_name: str) -> str:
    """Get container ID for a service"""
    result = subprocess.run(
        "docker compose ps -q rest_service", shell=True, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise Exception(
            f"Failed to get container ID for {service_name}: {result.stderr}"
        )
    return result.stdout.strip()


def create_migration(message: str):
    """Create a new migration"""
    # Get the container ID
    container_id = get_service_container("rest_service")

    # Create migration in the container
    result = subprocess.run(
        f'docker exec {container_id} python manage.py revision --autogenerate "{message}"',
        shell=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Failed to create migration: {result.stderr}")
        return result.returncode

    # Find the newly created migration file in the container
    result = subprocess.run(
        (
            f"docker exec {container_id} bash -c "
            '"ls -t /alembic/versions/*.py | head -1"'
        ),
        shell=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Failed to find migration file: {result.stderr}")
        return result.returncode
    container_file = result.stdout.strip()

    # Copy the migration file from container to host
    result = subprocess.run(
        f"docker cp {container_id}:{container_file} rest_service/alembic/versions/",
        shell=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Failed to copy migration file: {result.stderr}")
        return result.returncode

    return 0


def apply_migrations() -> int:
    """Apply all pending migrations."""
    return run_command("docker compose exec rest_service python manage.py upgrade")


def upgrade_one_step() -> int:
    """Apply the next pending migration."""
    return run_command("docker compose exec rest_service python manage.py upgrade +1")


def get_current_revision() -> int:
    """Show the current revision in the database."""
    return run_command("docker compose exec rest_service python manage.py current")


def get_migration_history() -> int:
    """Show the Alembic migration history."""
    return run_command("docker compose exec rest_service python manage.py history")


def run_tests(service: Optional[str] = None) -> int:
    """Run tests for all services or a specific service."""
    if service:
        return run_command(f"docker compose exec {service} python -m pytest")
    return run_command("docker compose exec rest_service python -m pytest")


def rebuild_containers(service: Optional[str] = None) -> int:
    """Rebuild all containers or a specific service."""
    if service:
        return run_command(f"docker compose build {service} && docker compose up -d")
    return run_command("docker compose build && docker compose up -d")


def restart_service(service: Optional[str] = None) -> int:
    """Stop a service, rebuild all containers,
    and start the service in detached mode."""
    if service:
        return run_command(
            f"docker compose stop {service} && "
            "docker compose build && docker compose up -d"
        )
    return run_command(
        "docker compose down && " "docker compose build && docker compose up -d"
    )


def start_service(service: Optional[str] = None) -> int:
    """Start a service in detached mode."""
    if service:
        return run_command(f"docker compose up -d {service}")
    return run_command("docker compose up -d")


def stop_service(service: Optional[str] = None) -> int:
    """Stop a service."""
    if service:
        return run_command(f"docker compose stop {service}")
    return run_command("docker compose down")


def run_black(service: Optional[str] = None) -> int:
    """Run black formatter for all services or a specific service."""
    if service:
        return run_command(f"black {service}/src")
    return run_command("black */src")


def run_isort(service: Optional[str] = None) -> int:
    """Run isort formatter for all services or a specific service."""
    if service:
        return run_command(f"isort {service}/src")
    return run_command("isort */src")


def main():
    parser = argparse.ArgumentParser(description="Manage the project")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create migration command
    migrate_parser = subparsers.add_parser("migrate", help="Create a new migration")
    migrate_parser.add_argument("message", help="Migration message")

    # Apply migrations command
    subparsers.add_parser("upgrade", help="Apply all pending migrations")

    # Apply one migration step command
    subparsers.add_parser("upgrade-step", help="Apply the next pending migration")

    # Show current revision command
    subparsers.add_parser("current", help="Show the current database revision")

    # Show migration history command
    subparsers.add_parser("history", help="Show the migration history")

    # Run tests command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("--service", help="Service to test")

    # Rebuild containers command
    rebuild_parser = subparsers.add_parser("rebuild", help="Rebuild containers")
    rebuild_parser.add_argument("--service", help="Service to rebuild")

    # Restart service command
    restart_parser = subparsers.add_parser("restart", help="Restart a service")
    restart_parser.add_argument("--service", help="Service to restart")

    # Start service command
    start_parser = subparsers.add_parser("start", help="Start a service")
    start_parser.add_argument("--service", help="Service to start")

    # Stop service command
    stop_parser = subparsers.add_parser("stop", help="Stop a service")
    stop_parser.add_argument("--service", help="Service to stop")

    # Run black command
    black_parser = subparsers.add_parser("black", help="Run black formatter")
    black_parser.add_argument("--service", help="Service to format")

    # Run isort command
    isort_parser = subparsers.add_parser("isort", help="Run isort formatter")
    isort_parser.add_argument("--service", help="Service to format")

    args = parser.parse_args()

    if args.command == "migrate":
        return create_migration(args.message)
    elif args.command == "upgrade":
        return apply_migrations()
    elif args.command == "upgrade-step":
        return upgrade_one_step()
    elif args.command == "current":
        return get_current_revision()
    elif args.command == "history":
        return get_migration_history()
    elif args.command == "test":
        return run_tests(args.service)
    elif args.command == "rebuild":
        return rebuild_containers(args.service)
    elif args.command == "restart":
        return restart_service(args.service)
    elif args.command == "start":
        return start_service(args.service)
    elif args.command == "stop":
        return stop_service(args.service)
    elif args.command == "black":
        return run_black(args.service)
    elif args.command == "isort":
        return run_isort(args.service)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
