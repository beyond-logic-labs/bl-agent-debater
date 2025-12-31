#!/usr/bin/env python3
"""
bl-debater CLI - Coordinate structured debates between any AI agents.

Usage:
    bl-debater start <name> -p "prompt" --as <role> --vs <role>
    bl-debater join <name> --as <role>
    bl-debater wait <name> --as <role>
    bl-debater watch <name>              # Live terminal UI
    bl-debater status <name>
    bl-debater list
    bl-debater roles
"""

import argparse
import sys
from pathlib import Path

from .debate import DebateManager
from .formatting import print_error, print_success, print_info, print_header

def cmd_start(args):
    """Create a new debate."""
    manager = DebateManager(args.debates_dir)

    try:
        debate_file, instructions = manager.start(
            name=args.name,
            prompt=args.prompt,
            role=args.role,
            opponent_role=args.vs,
            min_agreement=args.agreement
        )

        print_header("DEBATE CREATED")
        print_info(f"File: {debate_file}")
        print_info(f"You are: {args.role.upper()}")
        print_info(f"Opponent: {args.vs.upper()}")
        print_info(f"Consensus at: {args.agreement}%")
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
    from .debate import ROLES_DIR

    print_header("AVAILABLE ROLES")

    if not ROLES_DIR.exists():
        print_info("No roles directory found.")
        return

    roles = sorted(ROLES_DIR.glob("*.md"))

    if not roles:
        print_info("No roles defined.")
        return

    for role_file in roles:
        role_name = role_file.stem
        # Read first non-empty, non-heading line as description
        content = role_file.read_text()
        desc = ""
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                # Get first sentence or phrase
                desc = line.split(".")[0].replace("**", "").replace("You are a ", "").replace("You are an ", "")
                break
        print(f"  {role_name:15} {desc}")

def main():
    parser = argparse.ArgumentParser(
        prog="bl-debater",
        description="Coordinate structured debates between AI agents"
    )

    parser.add_argument(
        "--debates-dir",
        type=Path,
        default=Path.cwd() / "debates",
        help="Directory for debate files (default: ./debates)"
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
    wait_parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds (default: 600)")
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

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
