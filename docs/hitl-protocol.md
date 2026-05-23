# HITL Protocol

Every external action — sending an email, submitting an offer, signing a document — is preceded by an explicit user approval. The HITL (Human-in-the-Loop) system encodes this as a GitHub Issue label and a structured comment.

## How it works

1. The agent posts a HITL comment describing what it has prepared.
2. The agent adds a `hitl:<kind>` label to the issue.
3. The user reads the comment and replies with a slash-command.
4. The `on_comment.yml` workflow processes the reply and removes the label.

## Slash commands

| Command | Effect |
|---------|--------|
| `/approve` | Approves the pending task; may advance state |
| `/reject` | Rejects the pending task; may return to previous state |
| `/counter <amount>` | Records a counter-offer amount; re-queues approve_offer |
| `/like <property_id>` | Adds property to liked list |
| `/skip <property_id>` | Removes property from shortlist |
| `/note <text>` | Records context for the next agent pass |
| `/abort` | Purges encrypted PII and closes workflow |

## HITL catalogue

| Label | What the agent prepared | User action |
|-------|------------------------|-------------|
| `hitl:review_shortlist` | Top-N ranked properties | `/like` or `/skip` each |
| `hitl:approve_viewing` | Draft viewing request emails | `/approve` or add `/note` with availability |
| `hitl:approve_offer` | Draft offer letter | `/approve` (generates submission package) |
| `hitl:submit_offer_to_agent` | Ready-to-send email package | User sends from own email, replies `/approve` |
| `hitl:counter_decision` | Parsed seller counter | `/approve`, `/counter <amount>`, `/reject` |
| `hitl:lease_review` | Lease summary and redline | `/approve` to proceed to e-sign |
| `hitl:landlord_decision` | Submitted rental application | `/approve` or `/reject` based on landlord response |
| `hitl:payment_confirmation` | Bank wire instructions | Upload receipt, `/approve` |

## Guarantees

- The agent never sends an email, contacts a third party, or advances past a HITL checkpoint without an explicit slash-command.
- The `/abort` command always works, regardless of state. It zeroes the encrypted PII block and closes the issue.
- HITL labels are orthogonal to state labels; both can be present simultaneously.
