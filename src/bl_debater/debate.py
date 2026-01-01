"""Debate file management and coordination."""

import re
import time
import os
import subprocess
import tempfile
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional

# Try to import yaml, but make it optional
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def _get_roles_dirs() -> list[Path]:
    """Get list of directories to search for role definitions."""
    dirs = []

    # 1. CWD/roles (user's project-specific roles)
    cwd_roles = Path.cwd() / "roles"
    if cwd_roles.exists():
        dirs.append(cwd_roles)

    # 2. ~/.bl-debater/roles (user's global roles)
    home_roles = Path.home() / ".bl-debater" / "roles"
    if home_roles.exists():
        dirs.append(home_roles)

    # 3. Package bundled roles (inside the package)
    pkg_roles = Path(__file__).parent / "roles"
    if pkg_roles.exists():
        dirs.append(pkg_roles)

    return dirs


# For backward compatibility
ROLES_DIR = Path(__file__).parent / "roles"
ROLES_YAML_DIR = ROLES_DIR


def load_role_definition(role: str) -> Optional[str]:
    """Load role definition from file if it exists (supports .md and .yaml).

    Returns None if role is not defined - callers must handle this.
    """
    for roles_dir in _get_roles_dirs():
        # Try YAML first (new format) - only if yaml is available
        if YAML_AVAILABLE:
            yaml_file = roles_dir / f"{role}.yaml"
            if yaml_file.exists():
                try:
                    data = yaml.safe_load(yaml_file.read_text())
                    return _format_role_from_yaml(data)
                except Exception:
                    pass

        # Try markdown
        md_file = roles_dir / f"{role}.md"
        if md_file.exists():
            return md_file.read_text().strip()

    return None


def get_roles_dirs_for_creation() -> Path:
    """Get the preferred directory for creating new roles."""
    # Prefer ~/.bl-debater/roles for persistence
    home_roles = Path.home() / ".bl-debater" / "roles"
    home_roles.mkdir(parents=True, exist_ok=True)
    return home_roles


def create_role_definition(role: str, description: str, expertise: list[str],
                          debate_style: list[str], principles: list[str]) -> Path:
    """Create a new role definition file.

    Args:
        role: Role name (must be lowercase letters, numbers, hyphens only)
        description: Short description of the role
        expertise: List of expertise areas
        debate_style: List of debate style traits
        principles: List of key principles

    Returns:
        Path to the created role file

    Raises:
        ValueError: If role name contains invalid characters
        FileExistsError: If role already exists
    """
    import re

    # Validate role name to prevent path traversal
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', role):
        raise ValueError(
            f"Invalid role name '{role}'. "
            "Use only lowercase letters, numbers, and hyphens (not at start/end)."
        )

    roles_dir = get_roles_dirs_for_creation()
    role_file = roles_dir / f"{role}.md"

    if role_file.exists():
        raise FileExistsError(f"Role '{role}' already exists at {role_file}")

    content = f"""# {role.replace('-', ' ').title()}

{description}

## Expertise
{chr(10).join(f'- {e}' for e in expertise)}

## Debate Style
{chr(10).join(f'- {s}' for s in debate_style)}

## Key Principles
{chr(10).join(f'- {p}' for p in principles)}
"""
    role_file.write_text(content)
    return role_file


def _format_role_from_yaml(data: dict) -> str:
    """Format a YAML role definition into markdown."""
    lines = []

    if data.get("description"):
        lines.append(f"**{data['description']}**")
        lines.append("")

    if data.get("expertise"):
        lines.append("**Expertise:**")
        for item in data["expertise"]:
            lines.append(f"- {item}")
        lines.append("")

    if data.get("evaluation_criteria"):
        lines.append("**Evaluation Criteria:**")
        for item in data["evaluation_criteria"]:
            lines.append(f"- {item}")
        lines.append("")

    if data.get("style"):
        lines.append(f"**Style:** {data['style']}")

    return "\n".join(lines) if lines else f"Expert in {data.get('name', 'unknown')}"


def fetch_url_content(url: str, max_size: int = 100000) -> str:
    """Fetch content from a URL. Returns markdown-formatted content."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "bl-debater/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read(max_size).decode("utf-8", errors="replace")
            return f"### Content from {url}\n\n```\n{content[:max_size]}\n```"
    except urllib.error.URLError as e:
        return f"### Failed to fetch {url}\n\nError: {e}"
    except Exception as e:
        return f"### Failed to fetch {url}\n\nError: {e}"


def read_file_content(path: str) -> str:
    """Read content from a file path. Returns markdown-formatted content."""
    p = Path(path)
    if not p.exists():
        return f"### File not found: {path}"

    try:
        content = p.read_text()
        # Determine language for syntax highlighting
        ext = p.suffix.lower()
        lang_map = {
            ".py": "python", ".go": "go", ".js": "javascript",
            ".ts": "typescript", ".rs": "rust", ".yaml": "yaml",
            ".yml": "yaml", ".json": "json", ".md": "markdown",
            ".sh": "bash", ".sql": "sql"
        }
        lang = lang_map.get(ext, "")
        return f"### Content from {path}\n\n```{lang}\n{content}\n```"
    except Exception as e:
        return f"### Failed to read {path}\n\nError: {e}"

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
        participants_match = re.search(r"\*\*Participants:\*\*\s*([\w-]+)\s+vs\s+([\w-]+)", content)
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
            r"## Round \d+ - ([\w-]+).*?\*\*Agreement:\s*(\d+)%\*\*",
            content,
            re.DOTALL
        )
        for role, pct in agreement_matches:
            result["agreements"][role.lower()] = int(pct)

        return result

    def start(
        self,
        name: str,
        prompt: str,
        role: str,
        opponent_role: str,
        min_agreement: int = 80,
        context_items: list[str] | None = None
    ) -> tuple[Path, str]:
        """
        Create a new debate.

        Args:
            name: Debate name (used as filename)
            prompt: Problem statement
            role: Your role name
            opponent_role: Opponent's role name
            min_agreement: Minimum agreement % to reach consensus
            context_items: List of file paths or URLs to include as context

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

        # Build context section if items provided
        context_section = ""
        if context_items:
            context_parts = []
            for item in context_items:
                if item.startswith("http://") or item.startswith("https://"):
                    context_parts.append(fetch_url_content(item))
                else:
                    context_parts.append(read_file_content(item))
            context_section = "\n\n---\n\n## Context\n\n" + "\n\n".join(context_parts)

        content = f"""# Debate: {name}

**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Participants:** {role} vs {opponent_role}
**Consensus:** {min_agreement}%
**Status:** In Progress

---

## Problem Statement

{prompt}{context_section}

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

    def wait_for_turn(self, name: str, role: str, timeout: int = 60, poll_interval: float = 2.0) -> str:
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

    def get_response_template(self, name: str, role: str) -> tuple[str, Path]:
        """
        Generate a response template for the current turn.

        Returns:
            (template_content, debate_file_path)
        """
        debate_file = self._get_debate_path(name)

        if not debate_file.exists():
            raise ValueError(f"Debate '{name}' not found.")

        content = debate_file.read_text()
        parsed = self._parse_debate(content)

        role = role.lower()

        # Validate role and turn
        if role not in [parsed["role1"], parsed["role2"]]:
            raise ValueError(
                f"Role '{role}' is not a participant. "
                f"This debate is between {parsed['role1']} and {parsed['role2']}."
            )

        if parsed["current_turn"] != role:
            raise ValueError(f"Not your turn. Waiting for {parsed['current_turn']}.")

        if parsed["is_complete"]:
            raise ValueError("Debate is already complete.")

        opponent = parsed["role1"] if role == parsed["role2"] else parsed["role2"]
        round_num = parsed["round"]
        min_agreement = parsed.get("min_agreement", 80)

        # Check if this is the first response of the debate
        has_responses = bool(re.search(r"## Round \d+ - \w+", content))

        if not has_responses:
            # First response template
            template = f"""## Round {round_num} - {role.title()}

### Position
[Your initial stance on the problem]

### Key Points
[Main arguments - bullet points]

### Proposed Approach
[Your solution]

---

**Agreement: 0%**

{self._get_marker(opponent)}
"""
        else:
            # Response template
            template = f"""## Round {round_num} - {role.title()}

### Strengths
[What {opponent} got right - bullet points]

### Concerns
[Your disagreements - bullet points]

### Proposal
[Your solution/counter-proposal]

---

**Agreement: X%**

{self._get_marker(opponent)}

<!-- RULES:
- Replace X% with your actual agreement percentage
- If both agreements >= {min_agreement}%, add [PROPOSE_FINAL] with synthesis, then [CONFIRM?]
- If opponent wrote [CONFIRM?] and you agree: write [CONFIRMED] then [DEBATE_COMPLETE]
-->
"""

        return template, debate_file

    def respond_with_editor(self, name: str, role: str) -> bool:
        """
        Open editor with response template, validate and append to debate file.

        Returns:
            True if response was saved, False if cancelled
        """
        template, debate_file = self.get_response_template(name, role)

        # Create temp file with template
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            prefix=f"bl-debater-{name}-",
            delete=False
        ) as f:
            f.write(template)
            temp_path = f.name

        try:
            # Get editor from environment
            editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))

            # Open editor
            result = subprocess.run([editor, temp_path])

            if result.returncode != 0:
                raise RuntimeError(f"Editor exited with code {result.returncode}")

            # Read response
            response = Path(temp_path).read_text()

            # Validate response structure
            validation_errors = self._validate_response(response, role)
            if validation_errors:
                raise ValueError(f"Invalid response format:\n" + "\n".join(f"  - {e}" for e in validation_errors))

            # Read current debate content and remove the waiting marker
            content = debate_file.read_text()
            marker = self._get_marker(role.lower())

            # Replace the marker with the response
            if marker in content:
                new_content = content.replace(marker, response)
                debate_file.write_text(new_content)
                return True
            else:
                raise ValueError(f"Marker {marker} not found in debate file. Is it your turn?")

        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

    def _validate_response(self, response: str, role: str) -> list[str]:
        """Validate response format. Returns list of errors (empty if valid)."""
        errors = []

        # Must have round header
        if not re.search(rf"## Round \d+ - {role.title()}", response, re.IGNORECASE):
            errors.append(f"Missing round header (## Round N - {role.title()})")

        # Must have agreement
        if "**Agreement:" not in response:
            errors.append("Missing **Agreement: X%**")

        # Must have a waiting marker for opponent
        if not re.search(r"\[WAITING_\w+\]", response):
            # Unless it's the final confirmation
            if "[DEBATE_COMPLETE]" not in response:
                errors.append("Missing opponent's [WAITING_...] marker or [DEBATE_COMPLETE]")

        return errors

    def export_synthesis(self, name: str, format: str = "github-comment") -> str:
        """
        Export the final synthesis in the specified format.

        Args:
            name: Debate name
            format: Output format (github-comment, markdown, json)

        Returns:
            Formatted synthesis content
        """
        debate_file = self._get_debate_path(name)

        if not debate_file.exists():
            raise ValueError(f"Debate '{name}' not found.")

        content = debate_file.read_text()
        parsed = self._parse_debate(content)

        if not parsed["is_complete"]:
            raise ValueError("Debate is not complete. Wait for [DEBATE_COMPLETE] marker.")

        # Extract synthesis section (between [PROPOSE_FINAL] and [CONFIRM?] or end)
        # Find markers that are on their own line (not inline in text)
        # Look for [PROPOSE_FINAL] at start of line or after newline
        propose_match = re.search(r'(?:^|\n)\s*\[PROPOSE_FINAL\]\s*\n', content)
        if not propose_match:
            raise ValueError("No [PROPOSE_FINAL] marker found on its own line in completed debate.")

        propose_end = propose_match.end()

        # Find the end marker (on its own line)
        end_patterns = [
            r'(?:^|\n)\s*\[CONFIRM\?\]\s*(?:\n|$)',
            r'(?:^|\n)\s*\[CONFIRMED\]\s*(?:\n|$)',
            r'(?:^|\n)\s*\[DEBATE_COMPLETE\]\s*(?:\n|$)'
        ]

        end_idx = len(content)
        for pattern in end_patterns:
            match = re.search(pattern, content[propose_end:])
            if match and (propose_end + match.start()) < end_idx:
                end_idx = propose_end + match.start()

        synthesis = content[propose_end:end_idx].strip()

        if not synthesis:
            raise ValueError("No synthesis content found after [PROPOSE_FINAL].")

        # Get final agreements
        final_agreements = parsed.get("agreements", {})
        avg_agreement = sum(final_agreements.values()) / len(final_agreements) if final_agreements else 0

        if format == "github-comment":
            return self._format_github_comment(name, synthesis, final_agreements, avg_agreement, parsed)
        elif format == "markdown":
            return synthesis
        elif format == "json":
            import json
            return json.dumps({
                "debate": name,
                "synthesis": synthesis,
                "agreements": final_agreements,
                "average_agreement": avg_agreement,
                "participants": [parsed["role1"], parsed["role2"]],
                "rounds": parsed["round"]
            }, indent=2)
        else:
            raise ValueError(f"Unknown format: {format}")

    def _format_github_comment(
        self,
        name: str,
        synthesis: str,
        agreements: dict,
        avg_agreement: float,
        parsed: dict
    ) -> str:
        """Format synthesis as a GitHub PR comment."""
        participants = f"{parsed['role1'].title()} vs {parsed['role2'].title()}"
        agreement_str = ", ".join(f"{k.title()}: {v}%" for k, v in agreements.items())

        return f"""## bl-debater Review: {name}

**Participants:** {participants}
**Consensus Reached:** {avg_agreement:.0f}% ({agreement_str})
**Rounds:** {parsed['round']}

---

{synthesis}

---

<sub>Generated by [bl-debater](https://github.com/beyond-logic-labs/bl-debater) - Adversarial AI Review Infrastructure</sub>
"""
