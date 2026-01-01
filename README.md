# bl-agent-debater

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Build](https://github.com/beyond-logic-labs/bl-agent-debater/actions/workflows/build.yml/badge.svg)](https://github.com/beyond-logic-labs/bl-agent-debater/actions/workflows/build.yml)
[![PyPI](https://img.shields.io/pypi/v/bl-agent-debater.svg)](https://pypi.org/project/bl-agent-debater/)

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  ██████╗ ██╗      ██████╗ ███████╗██████╗  █████╗ ████████╗███████╗   │
│  ██╔══██╗██║      ██╔══██╗██╔════╝██╔══██╗██╔══██╗╚══██╔══╝██╔════╝   │
│  ██████╔╝██║█████╗██║  ██║█████╗  ██████╔╝███████║   ██║   █████╗     │
│  ██╔══██╗██║╚════╝██║  ██║██╔══╝  ██╔══██╗██╔══██║   ██║   ██╔══╝     │
│  ██████╔╝███████╗ ██████╔╝███████╗██████╔╝██║  ██║   ██║   ███████╗   │
│  ╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝   │
│                                                                        │
│  Structured debates between AI agents                                  │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

One AI gives one perspective. Two AIs surface counterarguments, trade-offs, and keep each other honest.

> **When to use what:**
> - **Claude-only debates?** Use [claude-code-cookbook](https://github.com/wasabeef/claude-code-cookbook) directly — it has richer capabilities with subagents and built-in roles.
> - **Multi-agent debates?** Use **bl-debater** — it bridges different AI systems (Claude + Codex, Claude + GPT, etc.) via a file-based protocol.

> **Note:** Commands are executed by AI agents inside their CLI environments (Claude Code, Codex, or any LLM client with filesystem access). You ask your AI to run the commands — it handles the debate.

---

## Demo

<p align="center">
  <img src="docs/demo.gif" alt="bl-debater demo" />
  <br /><br />
  <a href="https://beyondlogiclabs.com/debater">
    <img src="https://img.shields.io/badge/Visit%20Website-beyondlogiclabs.com%2Fdebater-ff69b4?style=for-the-badge&labelColor=8A2BE2" alt="Visit Website" />
  </a>
</p>

---

## Example: debates/auth.md

```markdown
# Debate: auth

**Participants:** architect vs security
**Consensus:** 80%

---

## Round 1 - Architect

### Position
- JWTs are stateless, scale horizontally without session storage

### Key Points
- No database lookup per request
- Easy to distribute across microservices

### Proposal
- Use JWTs with 24-hour expiry

**Agreement: 0%**

[WAITING_SECURITY]

---

## Round 1 - Security

### Strengths
- Agree JWTs scale better horizontally

### Concerns
- JWTs can't be revoked without a blocklist
- 24-hour expiry is too long if credentials leak

### Proposal
- Short-lived access tokens (15 min) + server-side refresh tokens

**Agreement: 60%**

[WAITING_ARCHITECT]

---

## Round 2 - Architect

### Strengths
- Valid point on revocation — refresh tokens solve this

### Concerns
- None remaining

### Proposal
- Accept: 15-min JWTs + server-side refresh tokens

**Agreement: 85%**

[PROPOSE_FINAL]

## Final Synthesis

Short-lived JWTs (15 min) for stateless auth, with server-side
refresh tokens for revocation. Best of both approaches.

[CONFIRM?]

---

## Round 2 - Security

Confirmed.

[CONFIRMED]
[DEBATE_COMPLETE]
```

---

## Installation

```bash
pip install bl-agent-debater
```

Or install from source:

```bash
git clone https://github.com/beyond-logic-labs/bl-agent-debater.git
cd bl-agent-debater
pip install -e .
```

## Commands

| Command | Description |
|---------|-------------|
| `bl-debater start <name> -p "..." --as <role> --vs <role>` | Create debate |
| `bl-debater start ... --watch` | Create and immediately watch |
| `bl-debater join <name> --as <role>` | Join existing debate |
| `bl-debater wait <name> --as <role>` | Wait for your turn |
| `bl-debater watch <name>` | **Live terminal UI** |
| `bl-debater timeout <name> --as <role>` | End unresponsive debate |
| `bl-debater status <name>` | Check debate status |
| `bl-debater list` | List all debates |
| `bl-debater roles` | Show available roles |

## Roles

| Role | Focus |
|------|-------|
| `architect` | System design, scalability |
| `security` | Vulnerabilities, threat modeling |
| `frontend` | UI/UX, accessibility |
| `backend` | APIs, databases |
| `performance` | Optimization, caching |
| `qa` | Testing, edge cases |
| `reviewer` | Code quality |
| `analyzer` | Requirements, trade-offs |
| `mobile` | iOS/Android, offline-first |

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--agreement` | 80 | Consensus threshold % |
| `--debates-dir` | `./debates` | Debate files directory |
| `--timeout` | 600 | Wait timeout (seconds) |

## Protocol

1. Debates stored in `debates/<name>.md`
2. Each response ends with `[WAITING_<ROLE>]`
3. `wait` command polls until marker matches your role
4. At consensus: `[PROPOSE_FINAL]` → `[CONFIRM?]` + `[WAITING_<ROLE>]` → `[CONFIRMED]` → `[DEBATE_COMPLETE]`
5. Timeouts: `[TIMEOUT]` ends abandoned debates

## Live Watch Mode

Watch debates unfold in real-time from a third terminal:

```bash
bl-debater watch auth
bl-debater watch auth --plain  # Simple single-line output
```

Features:
- **Color-coded roles** — Each participant gets a distinct color
- **Progress bar** — Visual consensus tracking toward threshold
- **Live updates** — Auto-refreshes as agents write responses
- **Animated spinner** — Shows which role is being waited on
- **Statistics** — Duration, word count, round tracking
- **Environment-aware** — Automatic plain output for CI/non-TTY

```
▶ BL-DEBATER LIVE  │  auth.md
──────────────────────────────────────────
● ARCHITECT  vs  ● SECURITY  │  Round 2
Consensus: [████████████░░░░░░░░] 60% → 80%
──────────────────────────────────────────

╭─ Round 2 • ARCHITECT ───────────────────╮
│ Strengths                               │
│   • Valid point on revocation           │
│                                         │
│ Concerns                                │
│   • None remaining                      │
│                                         │
│ Agreement: 85%                          │
╰─────────────────────────────────────────╯

⠹ Waiting for SECURITY...
Watching: 2m 15s │ Ctrl+C to exit
```

**Plain mode** (auto-enabled in CI, non-TTY, or with `NO_COLOR`):
```
[auth] Round 2 | Waiting: SECURITY | Agreement: 60% -> 80% | 12:34:56
```

## Documentation

- [`docs/AGENT_GUIDE.md`](docs/AGENT_GUIDE.md) — Instructions for AI agents
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — How to contribute

## Limitations

- Single machine only (file-based)
- 2-second polling interval
- Manual command invocation required
- No conflict resolution for simultaneous writes

## Status

> **Experimental** — Working prototype exploring multi-agent debate patterns.

The vision: evolve into something like [claude-code-cookbook](https://github.com/wasabeef/claude-code-cookbook) but for **multi-agent collaboration**. Ready-to-use debate templates, role libraries, consensus strategies.

## Credits

- Role prompts adapted from [claude-code-cookbook](https://github.com/wasabeef/claude-code-cookbook) by wasabeef

## License

MIT
