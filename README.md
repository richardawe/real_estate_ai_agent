# Real Estate AI Agent

A serverless agentic system for real estate buying and renting. GitHub Issues are the workflow database; GitHub Actions are the compute; GitHub Pages hosts the frontend.

## Architecture

- **No server.** All compute runs in GitHub Actions on a schedule or `repository_dispatch`.
- **Issues as state.** Every user journey is a GitHub Issue with encrypted PII and YAML front-matter. Labels drive the state machine; comments are the audit log.
- **Deterministic decisions.** Pricing, affordability, and eligibility are Python code against versioned `rules/` YAML — never LLM judgement.
- **LLM for extraction and drafting only.** OpenRouter free models extract facts from free text and draft user-facing content. They never gate an action.
- **HITL before any external action.** No emails sent, no documents signed, nothing submitted without an explicit `/approve` comment.

## Quick start

```bash
pip install -e ".[dev]"
pytest
```

## Workflows

| Command | Effect |
|---------|--------|
| `/approve` | Approves the pending HITL task |
| `/reject` | Rejects it |
| `/counter <amount>` | Issues a counter-offer |
| `/like <property_id>` | Adds property to shortlist |
| `/skip <property_id>` | Removes from shortlist |
| `/abort` | Closes workflow and purges PII |

## Repository layout

```
engine/          Deterministic Python engine (crypto, state machine, pricing)
workflows_lib/   Functions invoked by GitHub Actions
adapters/        YAML configs for listing sources, offer forms, smart locks
rules/           Versioned YAML rule sets (thresholds, weights, checklists)
site/            Static GitHub Pages frontend
.github/         Issue templates and Actions workflows
```

See `docs/architecture.md` for full documentation.
