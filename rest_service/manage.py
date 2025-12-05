#!/usr/bin/env python
import os
import sys


def run_alembic_command(command: str, args: list[str]) -> None:
    """Run alembic command with given arguments."""
    os.environ.setdefault("PYTHONPATH", "/app")
    from alembic import command as alembic_commands
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    # alembic_cfg.set_main_option("script_location", "/app/alembic")

    if command == "revision":
        # Find the message correctly, considering the --autogenerate flag
        message = None
        autogenerate = False
        try:
            if "--autogenerate" in args:
                autogenerate = True
                autogen_index = args.index("--autogenerate")
                # Message is the argument after the flag, if it exists
                if autogen_index + 1 < len(args):
                    message = args[autogen_index + 1]
            elif len(args) > 0:
                # If no --autogenerate, assume first arg is message
                message = args[0]

            if not message:
                print("Error: Migration message is required.")
                print("Usage: python manage.py revision --autogenerate <message>")
                sys.exit(1)

            # Call alembic command
            alembic_commands.revision(
                alembic_cfg, message=message, autogenerate=autogenerate
            )

        except ValueError:
            print("Error parsing arguments for revision command.")
            sys.exit(1)
    elif command == "upgrade":
        # Use provided revision or default to 'head'
        revision = args[0] if args else "head"
        alembic_commands.upgrade(alembic_cfg, revision)
    elif command == "downgrade":
        # Use provided revision or default to '-1'
        revision = args[0] if args else "-1"
        alembic_commands.downgrade(alembic_cfg, revision)
    elif command == "current":
        alembic_commands.current(alembic_cfg)
    elif command == "history":
        alembic_commands.history(alembic_cfg)
    else:
        print(f"Unknown alembic command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage.py <command> [args...]")
        print("Available commands:")
        print("  migrate <message> - Create a new migration")
        print(
            "  upgrade [revision] - Apply migrations "
            "(default: head, use '+1' for one step)"
        )
        print("  downgrade [revision] - Rollback migrations (default: -1)")
        print("  current - Show current migration")
        print("  history - Show migration history")
        sys.exit(1)

    command_arg = sys.argv[1]
    # Pass remaining args to the command function
    args_to_pass = sys.argv[2:]

    run_alembic_command(command_arg, args_to_pass)
