"""Debate file management and coordination."""

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Load role definitions from roles/ directory if available
ROLES_DIR = Path(__file__).parent.parent.parent / "roles"

def load_role_definition(role: str) -> str:
    """Load role definition from file if it exists."""
    role_file = ROLES_DIR / f"{role}.md"
    if role_file.exists():
        return role_file.read_text().strip()
    return f"Expert in {role}"

class DebateManager:
    """Manages debate files and coordination."""

    def __init__(self, debates_dir: Path):
        self.debates_dir = Path(debates_dir)
        self.debates_dir.mkdir(parents=True, exist_ok=True)

    def _get_debate_path(self, name: str) -> Path:
        """Get path to debate file."""
        # Normalize name (remove .md if present)
        name = name.replace(".md", "")
        return self.debates_dir / f"{name}.md"

    def _get_marker(self, role: str) -> str:
        """Get the waiting marker for a role."""
        return f"[WAITING_{role.upper()}]"

    def _parse_debate(self, content: str) -> dict:
        """Parse debate file content."""
        result = {
            "role1": None,
            "role2": None,
            "round": 1,
            "current_turn": None,
            "is_complete": False,
            "agreements": {},
            "min_agreement": 80  # default
        }

        # Check completion - must be on its own line (not in backticks/code)
        # Match [DEBATE_COMPLETE] that's NOT preceded by backtick
        if re.search(r"(?<!`)\[DEBATE_COMPLETE\](?!`)", content):
            result["is_complete"] = True

        # Find participants
        participants_match = re.search(r"\*\*Participants:\*\*\s*(\w+)\s+vs\s+(\w+)", content)
        if participants_match:
            result["role1"] = participants_match.group(1).lower()
            result["role2"] = participants_match.group(2).lower()

        # Find consensus threshold
        consensus_match = re.search(r"\*\*Consensus:\*\*\s*(\d+)%", content)
        if consensus_match:
            result["min_agreement"] = int(consensus_match.group(1))

        # Find current turn
        for role in [result["role1"], result["role2"]]:
            if role and self._get_marker(role) in content:
                result["current_turn"] = role
                break

        # Count rounds
        round_matches = re.findall(r"### Round (\d+)", content)
        if round_matches:
            result["round"] = max(int(r) for r in round_matches)

        # Find agreements
        agreement_matches = re.findall(
            r"## Round \d+ - (\w+).*?\*\*Agreement:\s*(\d+)%\*\*",
            content,
            re.DOTALL
        )
        for role, pct in agreement_matches:
            result["agreements"][role.lower()] = int(pct)

        return result

    def start(self, name: str, prompt: str, role: str, opponent_role: str, min_agreement: int = 80) -> tuple[Path, str]:
        """
        Create a new debate.

        Returns:
            (debate_file_path, instructions_for_agent)
        """
        debate_file = self._get_debate_path(name)

        if debate_file.exists():
            raise ValueError(f"Debate '{name}' already exists. Use 'join' instead.")

        role = role.lower()
        opponent_role = opponent_role.lower()

        role_def = load_role_definition(role)
        opponent_def = load_role_definition(opponent_role)

        content = f"""# Debate: {name}

**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Participants:** {role} vs {opponent_role}
**Consensus:** {min_agreement}%
**Status:** In Progress

---

## Problem Statement

{prompt}

---

## Role Definitions

### {role.title()}
{role_def}

### {opponent_role.title()}
{opponent_def}

---

## Transcript

### Round 1

{self._get_marker(role)}
"""

        debate_file.write_text(content)

        instructions = self._get_turn_instructions(role, opponent_role, 1, is_first=True, min_agreement=min_agreement)

        return debate_file, instructions

    def join(self, name: str, role: str) -> tuple[Path, str, bool]:
        """
        Join an existing debate.

        Returns:
            (debate_file_path, instructions, is_your_turn)
        """
        debate_file = self._get_debate_path(name)

        if not debate_file.exists():
            raise ValueError(f"Debate '{name}' not found. Use 'start' to create it.")

        content = debate_file.read_text()
        parsed = self._parse_debate(content)

        role = role.lower()

        # Validate role is in this debate
        if role not in [parsed["role1"], parsed["role2"]]:
            raise ValueError(
                f"Role '{role}' is not a participant. "
                f"This debate is between {parsed['role1']} and {parsed['role2']}."
            )

        is_your_turn = parsed["current_turn"] == role
        opponent = parsed["role1"] if role == parsed["role2"] else parsed["role2"]
        min_agreement = parsed.get("min_agreement", 80)

        instructions = self._get_turn_instructions(role, opponent, parsed["round"], is_first=False, min_agreement=min_agreement)

        return debate_file, instructions, is_your_turn

    def wait_for_turn(self, name: str, role: str, timeout: int = 300, poll_interval: float = 2.0) -> str:
        """
        Block until it's the specified role's turn.

        Returns:
            "YOUR_TURN" or "COMPLETE"
        """
        debate_file = self._get_debate_path(name)
        role = role.lower()
        marker = self._get_marker(role)

        start_time = time.time()

        while True:
            if not debate_file.exists():
                raise ValueError(f"Debate '{name}' not found.")

            content = debate_file.read_text()

            # Check for actual marker (not in backticks/code examples)
            if re.search(r"(?<!`)\[DEBATE_COMPLETE\](?!`)", content):
                return "COMPLETE"

            # Check for our turn marker (not in backticks)
            if re.search(rf"(?<!`){re.escape(marker)}(?!`)", content):
                return "YOUR_TURN"

            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Timeout after {timeout}s waiting for turn")

            time.sleep(poll_interval)

    def get_status(self, name: str) -> dict:
        """Get current debate status."""
        debate_file = self._get_debate_path(name)

        if not debate_file.exists():
            raise ValueError(f"Debate '{name}' not found.")

        content = debate_file.read_text()
        parsed = self._parse_debate(content)

        # Generate summary
        summary_lines = []
        if parsed["is_complete"]:
            summary_lines.append("Debate concluded successfully.")
        else:
            summary_lines.append(f"Round {parsed['round']} - Waiting for {parsed['current_turn']}")

        parsed["file"] = str(debate_file)
        parsed["summary"] = "\n".join(summary_lines)

        return parsed

    def list_debates(self) -> list[dict]:
        """List all debates."""
        debates = []

        for f in sorted(self.debates_dir.glob("*.md")):
            try:
                content = f.read_text()
                parsed = self._parse_debate(content)
                parsed["name"] = f.stem
                parsed["file"] = str(f)
                debates.append(parsed)
            except Exception:
                continue

        return debates

    def _get_turn_instructions(self, role: str, opponent: str, round_num: int, is_first: bool, min_agreement: int = 80) -> str:
        """Generate instructions for the current turn."""

        if is_first:
            return f"""Read the debate file and write your opening argument.

Your response format:

## Round {round_num} - {role.title()}

### Position
- [Your initial stance on the problem]

### Key Points
- [Main arguments]

### Proposed Approach
- [Your solution]

---

**Agreement: 0%**

{self._get_marker(opponent)}

---
After writing your response to the debate file, run:
  bl-debater wait <debate_name> --as {role}
"""

        return f"""Read the debate file and respond to your opponent.

Your response format:

## Round {round_num} - {role.title()}

### Strengths
- [What {opponent} got right]

### Concerns
- [Your disagreements]

### Proposal
- [Your solution/counter-proposal]

---

**Agreement: X%**

{self._get_marker(opponent)}

---
RULES:
- If both agreements >= {min_agreement}%, write [PROPOSE_FINAL] with synthesis, then [CONFIRM?]
- If opponent wrote [CONFIRM?] and you agree: write [CONFIRMED] then [DEBATE_COMPLETE]

After writing your response to the debate file, run:
  bl-debater wait <debate_name> --as {role}
"""
