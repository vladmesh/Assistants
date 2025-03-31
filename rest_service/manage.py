#!/usr/bin/env python
import os
import sys
from typing import List


def run_alembic_command(args: List[str]) -> None:
    """Run alembic command with given arguments."""
    os.environ.setdefault("PYTHONPATH", "/app")
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    alembic_cfg = Config("alembic.ini")
    command = args[0]

    if command == "revision":
        from alembic.command import revision

        message = args[2]
        revision(alembic_cfg, message=message, autogenerate=True)
    elif command == "upgrade":
        from alembic.command import upgrade

        upgrade(alembic_cfg, "head")
    elif command == "downgrade":
        from alembic.command import downgrade

        revision = args[1] if len(args) > 1 else "-1"
        downgrade(alembic_cfg, revision)
    elif command == "current":
        from alembic.command import current

        current(alembic_cfg)
    elif command == "history":
        from alembic.command import history

        history(alembic_cfg)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage.py <command> [args...]")
        print("Available commands:")
        print("  migrate - Create a new migration")
        print("  upgrade - Apply migrations")
        print("  downgrade - Rollback migrations")
        print("  current - Show current migration")
        print("  history - Show migration history")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "migrate":
        if not args:
            print("Usage: python manage.py migrate <message>")
            sys.exit(1)
        run_alembic_command(["revision", "--autogenerate", args[0]])
    elif command == "upgrade":
        run_alembic_command(["upgrade"])
    elif command == "downgrade":
        if not args:
            print("Usage: python manage.py downgrade <revision>")
            sys.exit(1)
        run_alembic_command(["downgrade", args[0]])
    elif command == "current":
        run_alembic_command(["current"])
    elif command == "history":
        run_alembic_command(["history"])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
