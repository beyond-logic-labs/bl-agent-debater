# Contributing to bl-debater

Thanks for your interest in contributing!

## Quick Start

1. Fork the repo
2. Create a branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests (`python -m pytest tests/`)
5. Submit a PR

## Testing

Run the suite with:

```bash
python -m pytest tests/
```

You should see all tests pass and a summary like `= 8 passed in 0.42s =`. When you need to explore different consensus thresholds, reuse `bl-debater start ... --agreement <percent>` in integration tests to verify agreement handling.

## Ways to Contribute

### Add New Roles
Create a new markdown file in `roles/`:

```markdown
# Role Name

You are a **Role Title** focused on [area of expertise].

## Key Priorities
1. ...

## You Evaluate
- ...

## You Advocate For
- ...
```

### Report Issues
Open a GitHub issue with:
- What you expected
- What happened
- Steps to reproduce

### Improve Docs
README improvements, examples, and tutorials are always welcome.

## Code Style

- Keep it simple — this project values minimal dependencies
- Follow existing patterns in the codebase
- Add tests for new functionality

## Governance

Owner: Beyond Logic Labs  
Primary reviewers: repository maintainers (see `OWNERS.md` if it exists or ask on issues)  
Security concerns: open a ticket via the GitHub Security tab or email security@beyondlogiclabs.com prior to public disclosure.

## Questions?

Open an issue or reach out to [Beyond Logic Labs](https://beyondlogiclabs.com).
