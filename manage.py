#!/usr/bin/env python3
import argparse
import subprocess
import sys
from typing import List, Optional

def run_command(command: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return its result."""
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, check=check)
    return result

def create_migration(message: str) -> None:
    """Create a new migration."""
    run_command(["docker", "compose", "exec", "rest_service", "python", "manage.py", "migrate", message])

def apply_migrations() -> None:
    """Apply all pending migrations."""
    run_command(["docker", "compose", "exec", "rest_service", "python", "manage.py", "upgrade"])

def run_tests(service: Optional[str] = None) -> None:
    """Run tests for all services or a specific service."""
    if service:
        run_command(["docker", "compose", "exec", service, "python", "-m", "pytest"])
    else:
        run_command(["docker", "compose", "exec", "rest_service", "python", "-m", "pytest"])

def rebuild_containers(service: Optional[str] = None) -> None:
    """Rebuild all containers or a specific service."""
    if service:
        run_command(["docker", "compose", "build", service])
    else:
        run_command(["docker", "compose", "build"])

def restart_service(service: str) -> None:
    """Stop service, rebuild all containers, and start service in detached mode."""
    run_command(["docker", "compose", "stop", service])
    run_command(["docker", "compose", "build"])
    run_command(["docker", "compose", "up", "-d"])

def start_service(service: str) -> None:
    """Start a service in detached mode."""
    run_command(["docker", "compose", "up", "-d", service])

def stop_service(service: str) -> None:
    """Stop a service."""
    run_command(["docker", "compose", "stop", service])

def main():
    parser = argparse.ArgumentParser(description="Manage Docker services and migrations")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create migration
    migrate_parser = subparsers.add_parser("migrate", help="Create a new migration")
    migrate_parser.add_argument("message", help="Migration message")

    # Apply migrations
    subparsers.add_parser("upgrade", help="Apply all pending migrations")

    # Run tests
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("--service", help="Service to test")

    # Rebuild containers
    rebuild_parser = subparsers.add_parser("rebuild", help="Rebuild containers")
    rebuild_parser.add_argument("--service", help="Service to rebuild")

    # Restart service
    restart_parser = subparsers.add_parser("restart", help="Restart service with rebuild")
    restart_parser.add_argument("service", help="Service to restart")

    # Start service
    start_parser = subparsers.add_parser("start", help="Start service")
    start_parser.add_argument("service", help="Service to start")

    # Stop service
    stop_parser = subparsers.add_parser("stop", help="Stop service")
    stop_parser.add_argument("service", help="Service to stop")

    args = parser.parse_args()

    if args.command == "migrate":
        create_migration(args.message)
    elif args.command == "upgrade":
        apply_migrations()
    elif args.command == "test":
        run_tests(args.service)
    elif args.command == "rebuild":
        rebuild_containers(args.service)
    elif args.command == "restart":
        restart_service(args.service)
    elif args.command == "start":
        start_service(args.service)
    elif args.command == "stop":
        stop_service(args.service)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main() 