#!/usr/bin/env python3
"""
bl-debater CLI - Coordinate structured debates between any AI agents.

Usage:
    bl-debater start <name> -p "prompt" --as <role> --vs <role> [--context file.md] [--context url]
    bl-debater respond <name> --as <role> [--template]
    bl-debater join <name> --as <role>
    bl-debater wait <name> --as <role>
    bl-debater watch <name>              # Live terminal UI
    bl-debater export <name> --format github-comment
    bl-debater status <name>
    bl-debater list
    bl-debater roles
"""

import argparse
import os
import sys
from pathlib import Path

from .debate import DebateManager, load_role_definition, get_roles_dirs_for_creation
from .formatting import print_error, print_success, print_info, print_header, print_warning


def _get_default_debates_dir() -> Path:
    """Get the default debates directory (cross-platform).

    Priority:
    1. BL_DEBATER_DIR environment variable
    2. ./debates (if exists in current directory)
    3. ~/.bl-debater/debates (default, works on Linux/macOS/Windows)
    """
    # Check environment variable first
    env_dir = os.environ.get("BL_DEBATER_DIR")
    if env_dir:
        return Path(env_dir)

    # Check if ./debates exists in current directory (project-specific)
    cwd_debates = Path.cwd() / "debates"
    if cwd_debates.exists():
        return cwd_debates

    # Default to ~/.bl-debater/debates (cross-platform home directory)
    return Path.home() / ".bl-debater" / "debates"


def _validate_role(role: str) -> bool:
    """Check if a role definition exists. Returns True if valid."""
    return load_role_definition(role) is not None


def _prompt_create_role(role: str) -> bool:
    """Prompt user to create a missing role definition. Returns True if created."""
    print_warning(f"Role '{role}' is not defined.")
    print_info("Roles must have a definition file. Would you like to create one?")
    print()

    try:
        response = input(f"Create {role}.md? [y/N]: ").strip().lower()
        if response != 'y':
            return False

        # Gather role info interactively
        print()
        print_info("Enter role details (press Enter for empty):")
        print()

        description = input("Description (1 line): ").strip() or f"Expert in {role}"

        print("Expertise (one per line, empty line to finish):")
        expertise = []
        while True:
            item = input("  - ").strip()
            if not item:
                break
            expertise.append(item)
        if not expertise:
            expertise = [f"{role} domain knowledge"]

        print("Debate style (one per line, empty line to finish):")
        style = []
        while True:
            item = input("  - ").strip()
            if not item:
                break
            style.append(item)
        if not style:
            style = ["Evidence-based argumentation"]

        print("Key principles (one per line, empty line to finish):")
        principles = []
        while True:
            item = input("  - ").strip()
            if not item:
                break
            principles.append(item)
        if not principles:
            principles = ["Clarity and precision"]

    except (EOFError, KeyboardInterrupt):
        print()
        print_info("Cancelled.")
        return False

    # Create the role file
    from .debate import create_role_definition
    try:
        role_file = create_role_definition(role, description, expertise, style, principles)
        print()
        print_success(f"Created: {role_file}")
        return True
    except ValueError as e:
        print_error(str(e))
        return False
    except FileExistsError as e:
        print_error(str(e))
        return False


def cmd_start(args):
    """Create a new debate."""
    manager = DebateManager(args.debates_dir)

    # Validate roles exist
    missing_roles = []
    for role in [args.role, args.vs]:
        if not _validate_role(role):
            missing_roles.append(role)

    if missing_roles:
        print_header("MISSING ROLE DEFINITIONS")
        print()
        for role in missing_roles:
            if not _prompt_create_role(role):
                print_error(f"Role '{role}' must be defined before starting a debate.")
                print_info(f"Create: ~/.bl-debater/roles/{role}.md")
                print_info("Or run: bl-debater roles  (to see available roles)")
                sys.exit(1)
        print()

    try:
        # Collect context items
        context_items = getattr(args, 'context', None) or []

        debate_file, instructions = manager.start(
            name=args.name,
            prompt=args.prompt,
            role=args.role,
            opponent_role=args.vs,
            min_agreement=args.agreement,
            context_items=context_items
        )

        print_header("DEBATE CREATED")
        print_info(f"File: {debate_file}")
        print_info(f"You are: {args.role.upper()}")
        print_info(f"Opponent: {args.vs.upper()}")
        print_info(f"Consensus at: {args.agreement}%")
        if context_items:
            print_info(f"Context: {len(context_items)} item(s) included")
        print()
        print_success("YOUR TURN!")
        print()
        print(instructions)

    except Exception as e:
        print_error(str(e))
        sys.exit(1)

def cmd_join(args):
    """Join an existing debate."""
    manager = DebateManager(args.debates_dir)

    try:
        debate_file, instructions, is_your_turn = manager.join(
            name=args.name,
            role=args.role
        )

        print_header("JOINED DEBATE")
        print_info(f"File: {debate_file}")
        print_info(f"You are: {args.role.upper()}")
        print()

        if is_your_turn:
            print_success("YOUR TURN!")
            print()
            print(instructions)
        else:
            print_info("Waiting for opponent...")
            # Block until it's our turn
            manager.wait_for_turn(args.name, args.role)
            print()
            print_success("YOUR TURN!")
            _, instructions, _ = manager.join(args.name, args.role)
            print()
            print(instructions)

    except Exception as e:
        print_error(str(e))
        sys.exit(1)

def cmd_wait(args):
    """Wait for your turn."""
    manager = DebateManager(args.debates_dir)

    try:
        print_info(f"Waiting for [WAITING_{args.role.upper()}]...")

        result = manager.wait_for_turn(args.name, args.role, timeout=args.timeout)

        if result == "COMPLETE":
            print_header("DEBATE COMPLETE")
            status = manager.get_status(args.name)
            print(status["summary"])
        elif result == "YOUR_TURN":
            print()
            print_success("YOUR TURN!")
            _, instructions, _ = manager.join(args.name, args.role)
            print()
            print(instructions)
        else:
            print_error(f"Unexpected result: {result}")
            sys.exit(1)

    except TimeoutError:
        print_error("Timeout waiting for turn")
        sys.exit(1)
    except Exception as e:
        print_error(str(e))
        sys.exit(1)

def cmd_status(args):
    """Show debate status."""
    manager = DebateManager(args.debates_dir)

    try:
        status = manager.get_status(args.name)

        print_header(f"DEBATE: {args.name}")
        print_info(f"File: {status['file']}")
        print_info(f"Participants: {status['role1']} vs {status['role2']}")
        print_info(f"Consensus at: {status.get('min_agreement', 80)}%")
        print_info(f"Round: {status['round']}")
        print_info(f"Current turn: {status['current_turn']}")

        if status.get('agreements'):
            print()
            print_info("Agreements:")
            for role, pct in status['agreements'].items():
                print(f"  {role}: {pct}%")

        print()
        if status['is_complete']:
            print_success("STATUS: COMPLETE")
        else:
            print_info(f"STATUS: Waiting for {status['current_turn'].upper()}")

    except Exception as e:
        print_error(str(e))
        sys.exit(1)

def cmd_list(args):
    """List all debates."""
    manager = DebateManager(args.debates_dir)

    debates = manager.list_debates()

    if not debates:
        print_info("No debates found.")
        return

    print_header("DEBATES")
    for d in debates:
        status_icon = "[DONE]" if d['is_complete'] else f"[R{d['round']}]"
        turn_info = "" if d['is_complete'] else f" <- {d['current_turn']}"
        print(f"  {d['name']:20} {status_icon:8} {d['role1']} vs {d['role2']}{turn_info}")

def cmd_watch(args):
    """Watch a debate live in the terminal."""
    from .watch import watch_debate

    debates_dir = args.debates_dir
    debate_path = debates_dir / f"{args.name.replace('.md', '')}.md"

    if not debate_path.exists():
        print_error(f"Debate '{args.name}' not found.")
        sys.exit(1)

    watch_debate(debate_path, poll_interval=args.interval)


def cmd_roles(args):
    """List available roles."""
    from .debate import _get_roles_dirs

    print_header("AVAILABLE ROLES")

    roles_dirs = _get_roles_dirs()
    if not roles_dirs:
        print_info("No roles directory found.")
        print_info("Create roles in: ./roles/, ~/.bl-debater/roles/")
        return

    # Collect roles from all directories
    roles_found = {}  # name -> (path, type)

    for roles_dir in roles_dirs:
        # Check markdown roles
        for role_file in sorted(roles_dir.glob("*.md")):
            role_name = role_file.stem
            if role_name in roles_found:
                continue
            content = role_file.read_text()
            desc = ""
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line.split(".")[0].replace("**", "").replace("You are a ", "").replace("You are an ", "")[:50]
                    break
            roles_found[role_name] = (desc, "md", roles_dir)

        # Check YAML roles (only if yaml is available)
        try:
            import yaml
            for role_file in sorted(roles_dir.glob("*.yaml")):
                role_name = role_file.stem
                if role_name in roles_found:
                    continue
                try:
                    data = yaml.safe_load(role_file.read_text())
                    desc = data.get("description", "")[:50]
                except:
                    desc = ""
                roles_found[role_name] = (desc, "yaml", roles_dir)
        except ImportError:
            pass  # YAML not available, skip YAML roles

    if not roles_found:
        print_info("No roles defined.")
        return

    for role_name in sorted(roles_found.keys()):
        desc, fmt, path = roles_found[role_name]
        tag = "[YAML]" if fmt == "yaml" else ""
        print(f"  {role_name:20} {desc} {tag}")


def cmd_respond(args):
    """Respond to the current turn with editor integration."""
    manager = DebateManager(args.debates_dir)

    try:
        if args.template:
            # Open editor with template
            print_info(f"Opening editor for {args.name}...")
            saved = manager.respond_with_editor(args.name, args.role)
            if saved:
                print_success("Response saved!")
                print()
                print_info("Run the following to wait for opponent:")
                print(f"  bl-debater wait {args.name} --as {args.role}")
        else:
            # Just show the template
            template, debate_file = manager.get_response_template(args.name, args.role)
            print_header("RESPONSE TEMPLATE")
            print_info(f"File: {debate_file}")
            print()
            print(template)
            print()
            print_info("Copy the above template and add it to the debate file.")
            print_info("Or run with --template to open in your $EDITOR.")

    except Exception as e:
        print_error(str(e))
        sys.exit(1)


def cmd_export(args):
    """Export the final synthesis."""
    manager = DebateManager(args.debates_dir)

    try:
        output = manager.export_synthesis(args.name, format=args.format)

        if args.output:
            # Write to file
            Path(args.output).write_text(output)
            print_success(f"Exported to {args.output}")
        else:
            # Print to stdout
            print(output)

    except Exception as e:
        print_error(str(e))
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        prog="bl-debater",
        description="Coordinate structured debates between AI agents"
    )

    parser.add_argument(
        "--debates-dir",
        type=Path,
        default=None,  # Will use _get_default_debates_dir() if not specified
        help="Directory for debate files (default: ~/.bl-debater/debates or ./debates if exists)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # start command
    start_parser = subparsers.add_parser("start", help="Create a new debate")
    start_parser.add_argument("name", help="Debate name (used as filename)")
    start_parser.add_argument("-p", "--prompt", required=True, help="Problem statement")
    start_parser.add_argument("--as", dest="role", required=True, help="Your role")
    start_parser.add_argument("--vs", required=True, help="Opponent's role")
    start_parser.add_argument("--agreement", type=int, default=80,
                              help="Minimum agreement %% to reach consensus (default: 80)")
    start_parser.add_argument("-c", "--context", action="append", metavar="PATH_OR_URL",
                              help="Include file or URL content as context (can be repeated)")
    start_parser.set_defaults(func=cmd_start)

    # join command
    join_parser = subparsers.add_parser("join", help="Join an existing debate")
    join_parser.add_argument("name", help="Debate name")
    join_parser.add_argument("--as", dest="role", required=True, help="Your role")
    join_parser.set_defaults(func=cmd_join)

    # wait command
    wait_parser = subparsers.add_parser("wait", help="Wait for your turn")
    wait_parser.add_argument("name", help="Debate name")
    wait_parser.add_argument("--as", dest="role", required=True, help="Your role")
    wait_parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds (default: 60)")
    wait_parser.set_defaults(func=cmd_wait)

    # status command
    status_parser = subparsers.add_parser("status", help="Show debate status")
    status_parser.add_argument("name", help="Debate name")
    status_parser.set_defaults(func=cmd_status)

    # list command
    list_parser = subparsers.add_parser("list", help="List all debates")
    list_parser.set_defaults(func=cmd_list)

    # roles command
    roles_parser = subparsers.add_parser("roles", help="List available roles")
    roles_parser.set_defaults(func=cmd_roles)

    # watch command
    watch_parser = subparsers.add_parser("watch", help="Watch a debate live with rich UI")
    watch_parser.add_argument("name", help="Debate name")
    watch_parser.add_argument("--interval", type=float, default=1.0,
                              help="Poll interval in seconds (default: 1.0)")
    watch_parser.set_defaults(func=cmd_watch)

    # respond command
    respond_parser = subparsers.add_parser("respond", help="Respond with editor integration")
    respond_parser.add_argument("name", help="Debate name")
    respond_parser.add_argument("--as", dest="role", required=True, help="Your role")
    respond_parser.add_argument("--template", "-t", action="store_true",
                                help="Open $EDITOR with pre-filled template")
    respond_parser.set_defaults(func=cmd_respond)

    # export command
    export_parser = subparsers.add_parser("export", help="Export synthesis from completed debate")
    export_parser.add_argument("name", help="Debate name")
    export_parser.add_argument("--format", "-f", default="github-comment",
                               choices=["github-comment", "markdown", "json"],
                               help="Output format (default: github-comment)")
    export_parser.add_argument("--output", "-o", metavar="FILE",
                               help="Write to file instead of stdout")
    export_parser.set_defaults(func=cmd_export)

    args = parser.parse_args()

    # Resolve default debates directory if not specified
    if args.debates_dir is None:
        args.debates_dir = _get_default_debates_dir()

    # Ensure debates directory exists
    args.debates_dir.mkdir(parents=True, exist_ok=True)

    args.func(args)

if __name__ == "__main__":
    main()
