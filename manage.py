#!/usr/bin/env python3
import argparse
import subprocess
import sys
from typing import List, Optional

def run_command(command: str) -> int:
    """Run a command and return its result."""
    try:
        result = subprocess.run(command, shell=True, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        return e.returncode

def create_migration(message: str) -> int:
    """Create a new migration."""
    return run_command(f"docker compose exec rest_service python manage.py migrate '{message}'")

def apply_migrations() -> int:
    """Apply all pending migrations."""
    return run_command("docker compose exec rest_service python manage.py upgrade")

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
    """Stop a service, rebuild all containers, and start the service in detached mode."""
    if service:
        return run_command(f"docker compose stop {service} && docker compose build && docker compose up -d")
    return run_command("docker compose down && docker compose build && docker compose up -d")

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

def main():
    parser = argparse.ArgumentParser(description="Manage the project")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create migration command
    migrate_parser = subparsers.add_parser("migrate", help="Create a new migration")
    migrate_parser.add_argument("message", help="Migration message")

    # Apply migrations command
    subparsers.add_parser("upgrade", help="Apply all pending migrations")

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

    args = parser.parse_args()

    if args.command == "migrate":
        return create_migration(args.message)
    elif args.command == "upgrade":
        return apply_migrations()
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
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 