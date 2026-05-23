# Architecture

## Principles

1. **No server.** All compute runs in GitHub Actions on a schedule or `repository_dispatch`. The frontend is a static site on GitHub Pages.
2. **Issues as the database.** Every user workflow is a GitHub Issue with YAML front-matter. Labels are the state machine; comments are the audit log.
3. **Deterministic where it matters.** Pricing comparisons, eligibility checks, budget math, fraud signals — all Python code against versioned YAML rule sets.
4. **LLM only for extraction and drafting.** OpenRouter free models extract structured facts from free text, draft emails, and summarise documents. They never decide.
5. **Humans confirm before any external action.** No emails sent, no documents signed, no listings contacted without an explicit `/approve` comment.
6. **PII encrypted in issues.** libsodium-encrypt PII fields before they're stored. Issue titles and labels contain `workflow_id` only.

## Data flow

```
User (browser)
  │ repository_dispatch / issue comment
  ▼
GitHub Actions (compute)
  ├── intake.yml ──► workflows_lib/intake.py ──► LLM extraction ──► issue front-matter
  ├── discover.yml ──► adapters_runtime/ ──► engine/eligibility + pricing ──► shortlist comment
  ├── on_comment.yml ──► on_comment.py ──► slash-command dispatch ──► state transition
  ├── advance.yml ──► advance_action.py ──► per-state tick
  └── nightly.yml ──► digest + archive + token budget alerts
  │
  ▼
GitHub Issues (state + audit log)
  │
  ▼
GitHub Pages (frontend polls Issues API every 15s)
```

## State machine

States are GitHub Issue labels with the prefix `state:`. Transitions are defined exhaustively in `engine/state_machine.py`. Nothing outside `state_machine.transition()` may add or remove state labels.

```
state:intake
  └──► state:discover
        └──► state:shortlist_review
              ├──► state:viewings (buy)
              │     └──► state:offer_draft
              │           └──► state:offer_submitted
              │                 └──► state:due_diligence
              │                       └──► state:closing
              │                             └──► state:completed
              └──► state:lease_review (rent)
                    └──► state:closing
                          └──► state:completed
```

Backward transitions for rejection: `offer_draft → shortlist_review`, `viewings → shortlist_review`.

## HITL tasks

Orthogonal to state, encoded as `hitl:<kind>` labels. The `on_comment.yml` workflow listens for slash-commands that complete them. See `docs/hitl-protocol.md` for the full catalogue.

## Concurrency

All workflows use `concurrency: workflow-<issue_number>` to prevent two ticks from mutating the same issue simultaneously.

## Token budget

Each LLM call returns a token count which is accumulated in `front-matter.token_usage`. The nightly workflow alerts when usage exceeds 500,000 tokens and pauses further LLM calls on that workflow.
