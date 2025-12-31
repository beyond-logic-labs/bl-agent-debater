"""Live debate watcher with rich terminal UI."""

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"

    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


# Role colors - alternating vibrant colors
ROLE_COLORS = [
    Colors.BRIGHT_CYAN,
    Colors.BRIGHT_MAGENTA,
    Colors.BRIGHT_YELLOW,
    Colors.BRIGHT_GREEN,
    Colors.BRIGHT_BLUE,
    Colors.BRIGHT_RED,
]


def get_role_color(role: str, roles: list) -> str:
    """Get consistent color for a role."""
    try:
        idx = roles.index(role.lower())
        return ROLE_COLORS[idx % len(ROLE_COLORS)]
    except (ValueError, IndexError):
        return Colors.WHITE


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_terminal_width() -> int:
    """Get terminal width, default to 80."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def draw_box(lines: list[str], width: int, title: str = "", color: str = Colors.WHITE) -> list[str]:
    """Draw a box around content."""
    inner_width = width - 4
    result = []

    # Top border with optional title
    if title:
        title_display = f" {title} "
        padding = inner_width - len(title) - 2
        left_pad = padding // 2
        right_pad = padding - left_pad
        top = f"{color}╭{'─' * left_pad}{Colors.BOLD}{title_display}{Colors.RESET}{color}{'─' * right_pad}╮{Colors.RESET}"
    else:
        top = f"{color}╭{'─' * (inner_width + 2)}╮{Colors.RESET}"
    result.append(top)

    # Content
    for line in lines:
        # Strip ANSI codes for length calculation
        visible_len = len(re.sub(r'\033\[[0-9;]*m', '', line))
        padding = inner_width - visible_len
        if padding < 0:
            # Truncate
            line = line[:inner_width - 3] + "..."
            padding = 0
        result.append(f"{color}│{Colors.RESET} {line}{' ' * padding} {color}│{Colors.RESET}")

    # Bottom border
    result.append(f"{color}╰{'─' * (inner_width + 2)}╯{Colors.RESET}")

    return result


def draw_progress_bar(current: int, target: int, width: int = 30) -> str:
    """Draw an ASCII progress bar."""
    if target == 0:
        target = 100

    percentage = min(current / target, 1.0)
    filled = int(width * percentage)
    empty = width - filled

    # Color based on progress
    if percentage >= 1.0:
        color = Colors.BRIGHT_GREEN
        symbol = "█"
    elif percentage >= 0.75:
        color = Colors.BRIGHT_YELLOW
        symbol = "█"
    elif percentage >= 0.5:
        color = Colors.YELLOW
        symbol = "▓"
    else:
        color = Colors.WHITE
        symbol = "▓"

    bar = f"{color}{symbol * filled}{Colors.DIM}{'░' * empty}{Colors.RESET}"
    return f"[{bar}] {current}% → {target}%"


def parse_rounds(content: str) -> list[dict]:
    """Parse debate content into rounds."""
    rounds = []

    # Find all round markers
    pattern = r"## Round \d+ - (\w+)(.*?)(?=## Round \d+|## Final|## Proposed|\[DEBATE_COMPLETE\]|\[PROPOSE_FINAL\]|$)"
    matches = re.findall(pattern, content, re.DOTALL)

    for role, body in matches:
        # Extract agreement
        agreement_match = re.search(r"\*\*Agreement:\s*(\d+)%\*\*", body)
        agreement = int(agreement_match.group(1)) if agreement_match else 0

        rounds.append({
            "role": role.lower(),
            "content": body.strip(),
            "agreement": agreement,
        })

    return rounds


def format_round_content(content: str, width: int, role_color: str) -> list[str]:
    """Format round content for display."""
    lines = []

    for line in content.split('\n'):
        line = line.rstrip()

        # Style headers
        if line.startswith('### '):
            header = line[4:]
            lines.append(f"{role_color}{Colors.BOLD}{header}{Colors.RESET}")
        elif line.startswith('- '):
            lines.append(f"  {Colors.DIM}•{Colors.RESET} {line[2:]}")
        elif line.startswith('**Agreement:'):
            # Skip, we show this separately
            pass
        elif line.startswith('[WAITING_') or line.startswith('[PROPOSE_') or line.startswith('[CONFIRM'):
            # Skip markers
            pass
        elif line.strip():
            lines.append(f"  {line}")

    return lines


class DebateWatcher:
    """Watch a debate in real-time with rich UI."""

    def __init__(self, debate_path: Path):
        self.debate_path = debate_path
        self.last_content = ""
        self.last_modified = 0
        self.start_time = time.time()
        self.role1 = None
        self.role2 = None
        self.consensus_target = 80
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0

    def parse_metadata(self, content: str):
        """Parse debate metadata."""
        # Participants
        match = re.search(r"\*\*Participants:\*\*\s*(\w+)\s+vs\s+(\w+)", content)
        if match:
            self.role1 = match.group(1).lower()
            self.role2 = match.group(2).lower()

        # Consensus target
        match = re.search(r"\*\*Consensus:\*\*\s*(\d+)%", content)
        if match:
            self.consensus_target = int(match.group(1))

    def get_waiting_role(self, content: str) -> Optional[str]:
        """Get which role is being waited on."""
        match = re.search(r"\[WAITING_(\w+)\](?!`)", content)
        if match:
            return match.group(1).lower()
        return None

    def is_complete(self, content: str) -> bool:
        """Check if debate is complete."""
        return bool(re.search(r"(?<!`)\[DEBATE_COMPLETE\](?!`)", content))

    def render(self, content: str):
        """Render the debate UI."""
        clear_screen()
        width = min(get_terminal_width(), 100)

        self.parse_metadata(content)
        rounds = parse_rounds(content)
        waiting_for = self.get_waiting_role(content)
        is_complete = self.is_complete(content)

        roles = [self.role1, self.role2] if self.role1 and self.role2 else []

        # Header
        print()
        print(f"  {Colors.BOLD}{Colors.BRIGHT_WHITE}▶ BL-DEBATER LIVE{Colors.RESET}  {Colors.DIM}│{Colors.RESET}  {Colors.DIM}{self.debate_path.name}{Colors.RESET}")
        print(f"  {Colors.DIM}{'─' * (width - 4)}{Colors.RESET}")

        # Participants & Status
        if self.role1 and self.role2:
            color1 = get_role_color(self.role1, roles)
            color2 = get_role_color(self.role2, roles)

            print(f"  {color1}{Colors.BOLD}● {self.role1.upper()}{Colors.RESET}  {Colors.DIM}vs{Colors.RESET}  {color2}{Colors.BOLD}● {self.role2.upper()}{Colors.RESET}  {Colors.DIM}│{Colors.RESET}  {Colors.DIM}Round {len(rounds)}{Colors.RESET}")

        # Progress bar
        if rounds:
            latest_agreement = rounds[-1]["agreement"]
            progress = draw_progress_bar(latest_agreement, self.consensus_target, width=30)
            print(f"  {Colors.DIM}Consensus:{Colors.RESET} {progress}")

        print(f"  {Colors.DIM}{'─' * (width - 4)}{Colors.RESET}")
        print()

        # Show last 2 rounds (or all if less)
        display_rounds = rounds[-2:] if len(rounds) > 2 else rounds

        for rnd in display_rounds:
            role = rnd["role"]
            role_color = get_role_color(role, roles)

            # Round header
            round_num = rounds.index(rnd) + 1
            title = f"Round {round_num} • {role.upper()}"

            # Format content
            content_lines = format_round_content(rnd["content"], width - 6, role_color)

            # Add agreement at bottom
            agreement = rnd["agreement"]
            if agreement >= self.consensus_target:
                agree_color = Colors.BRIGHT_GREEN
            elif agreement >= 60:
                agree_color = Colors.BRIGHT_YELLOW
            else:
                agree_color = Colors.WHITE
            content_lines.append("")
            content_lines.append(f"{agree_color}{Colors.BOLD}Agreement: {agreement}%{Colors.RESET}")

            # Draw box
            box = draw_box(content_lines, width - 4, title, role_color)
            for line in box:
                print(f"  {line}")
            print()

        # Status footer
        print(f"  {Colors.DIM}{'─' * (width - 4)}{Colors.RESET}")

        if is_complete:
            print(f"  {Colors.BRIGHT_GREEN}{Colors.BOLD}✓ DEBATE COMPLETE{Colors.RESET}")
            # Show final stats
            elapsed = time.time() - self.start_time
            word_count = len(content.split())
            print(f"  {Colors.DIM}Duration: {elapsed:.0f}s │ Words: {word_count} │ Rounds: {len(rounds)}{Colors.RESET}")
        elif waiting_for:
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_frames)
            spinner = self.spinner_frames[self.spinner_idx]
            wait_color = get_role_color(waiting_for, roles)
            print(f"  {Colors.BRIGHT_YELLOW}{spinner}{Colors.RESET} Waiting for {wait_color}{Colors.BOLD}{waiting_for.upper()}{Colors.RESET}...")
        else:
            print(f"  {Colors.DIM}Watching for changes...{Colors.RESET}")

        # Time elapsed
        elapsed = time.time() - self.start_time
        mins, secs = divmod(int(elapsed), 60)
        print(f"  {Colors.DIM}Watching: {mins}m {secs}s │ Ctrl+C to exit{Colors.RESET}")
        print()

    def watch(self, poll_interval: float = 1.0):
        """Start watching the debate."""
        if not self.debate_path.exists():
            print(f"{Colors.RED}Error: Debate file not found: {self.debate_path}{Colors.RESET}")
            sys.exit(1)

        print(f"{Colors.BRIGHT_CYAN}Starting live watch...{Colors.RESET}")
        time.sleep(0.5)

        try:
            while True:
                # Check for file changes
                current_modified = self.debate_path.stat().st_mtime

                if current_modified != self.last_modified:
                    self.last_modified = current_modified
                    content = self.debate_path.read_text()

                    if content != self.last_content:
                        self.last_content = content
                        self.render(content)

                        # Check if complete
                        if self.is_complete(content):
                            break
                else:
                    # Just update spinner
                    content = self.debate_path.read_text()
                    self.render(content)

                time.sleep(poll_interval)

        except KeyboardInterrupt:
            print(f"\n{Colors.DIM}Watch stopped.{Colors.RESET}")


def watch_debate(debate_path: Path, poll_interval: float = 1.0):
    """Main entry point for watching a debate."""
    watcher = DebateWatcher(debate_path)
    watcher.watch(poll_interval)
