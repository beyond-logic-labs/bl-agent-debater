# Agent Guide: How to Participate in a bl-debater Debate

This guide explains how AI agents (Claude Code, Codex, or any CLI-based LLM) should participate in structured debates using bl-debater.

## Overview

bl-debater is a CLI tool that coordinates turn-based debates between two AI agents. You communicate by reading and writing to a shared markdown file. The tool manages turn-taking through markers.

## Getting Started

### If you're starting a debate

```bash
bl-debater start <name> -p "<problem statement>" --as <your-role> --vs <opponent-role>
```

This creates `debates/<name>.md`. You go first.

### If you're joining a debate

```bash
bl-debater join <name> --as <your-role>
```

If it's your turn, you'll see instructions. If not, the command will wait until it's your turn.

## The Debate File

The debate file (`debates/<name>.md`) contains:

1. **Header** - Date, participants, consensus threshold
2. **Problem Statement** - What you're debating
3. **Role Definitions** - Your persona and your opponent's
4. **Transcript** - All rounds of the debate

Read the entire file before responding. Understand the problem, your role, and what your opponent has argued.

## How to Respond

### Round 1 (Opening)

Write your opening position:

```markdown
## Round 1 - <YourRole>

### Position
- Your initial stance on the problem

### Key Points
- Main arguments supporting your position
- Evidence or reasoning

### Proposed Approach
- Your recommended solution

---

**Agreement: 0%**

[WAITING_<OPPONENT_ROLE>]
```

### Subsequent Rounds

Respond to your opponent:

```markdown
## Round N - <YourRole>

### Strengths
- What your opponent got right
- Points you agree with

### Concerns
- Where you disagree
- Risks or issues with their proposal

### Proposal
- Your counter-proposal or refinement

---

**Agreement: X%**

[WAITING_<OPPONENT_ROLE>]
```

## Agreement Tracking

After each response, estimate your agreement percentage:

| Percentage | Meaning |
|------------|---------|
| 0-30% | Fundamental disagreement |
| 30-60% | Some common ground, major differences |
| 60-80% | Mostly aligned, details to resolve |
| 80-95% | Near consensus |
| 95-100% | Full agreement |

Be honest. The goal is to reach genuine consensus, not to "win."

## Reaching Consensus

When both agents reach the consensus threshold (default 80%):

### Step 1: Propose Final Synthesis

```markdown
## Round N - <YourRole>

### Strengths
- Final acknowledgments

### Concerns
- None remaining (or minor notes)

### Proposal
- Summary of agreed solution

---

**Agreement: 90%**

[PROPOSE_FINAL]

## Proposed Final Synthesis

**Decision:** <one-line summary>

**Key Points:**
- Point 1
- Point 2
- Point 3

**Rationale:**
<Why this is the right approach>

[CONFIRM?]
```

### Step 2: Confirm (Opponent's Turn)

When you see `[CONFIRM?]` and agree with the synthesis:

```markdown
## Round N - <YourRole>

The proposed synthesis accurately captures our consensus.

[CONFIRMED]

[DEBATE_COMPLETE]
```

If you don't agree, continue debating with another round instead.

## Turn Management

After writing your response to the debate file:

```bash
bl-debater wait <name> --as <your-role>
```

This blocks until it's your turn again or the debate completes.

## Markers Reference

| Marker | Meaning |
|--------|---------|
| `[WAITING_<ROLE>]` | It's <ROLE>'s turn to respond |
| `[PROPOSE_FINAL]` | Consensus reached, proposing synthesis |
| `[CONFIRM?]` | Asking opponent to confirm synthesis |
| `[CONFIRMED]` | Synthesis accepted |
| `[DEBATE_COMPLETE]` | Debate finished |

## Best Practices

1. **Read the full transcript** before responding
2. **Acknowledge valid points** from your opponent
3. **Be specific** about disagreements
4. **Propose solutions**, not just criticisms
5. **Update agreement honestly** based on actual alignment
6. **Stay in character** according to your role definition
7. **Be concise** - aim for clarity over length

## Example Flow

```
Terminal 1 (Architect)              Terminal 2 (Security)
─────────────────────               ─────────────────────
bl-debater start auth
  -p "JWT vs sessions"
  --as architect
  --vs security

[Writes Round 1]

bl-debater wait auth                bl-debater join auth
  --as architect                      --as security

[Waiting...]                        [Writes Round 1]

                                    bl-debater wait auth
                                      --as security

[Your turn!]                        [Waiting...]

[Writes Round 2]

bl-debater wait auth
  --as architect

[Waiting...]                        [Your turn!]

                                    [Writes Round 2 + PROPOSE_FINAL]

                                    bl-debater wait auth
                                      --as security

[Your turn!]                        [Waiting...]

[Writes CONFIRMED +
 DEBATE_COMPLETE]

bl-debater wait auth
  --as architect

[Debate Complete!]                  [Debate Complete!]
```

## Troubleshooting

**"Debate not found"** - Check the name matches exactly (case-sensitive)

**"Role not a participant"** - You're using a role that wasn't specified in `start`

**Timeout** - Increase with `--timeout 900` (15 minutes)

**Stuck waiting** - Your opponent may not have written their response yet. Check the debate file directly.
