# Privacy Notice

**Last updated:** 2026-05-23

## What we collect

When you start a buying or renting workflow, we ask for:

- Contact details (name, email, phone)
- Property requirements (budget, location, bedrooms)
- Financial information (income, deposit available) — buying only
- Identity documents — only when required by a specific HITL step

## How we store it

All personally identifiable information (PII) is encrypted with libsodium (XSalsa20-Poly1305) before being written to a GitHub Issue. The encryption key lives in GitHub Actions secrets and is never exposed to the browser or issue comments.

Issue titles and labels contain only an opaque `workflow_id`. No PII ever appears in plaintext in any GitHub UI.

## How we use it

Your data is used solely to operate your workflow:

- Requirements are matched against property listings
- Contact details are used to send viewing confirmations and offer correspondence
- Financial information is used for affordability calculations only

We do not sell, share, or use your data for advertising.

## Third-party services

- **GitHub** — issues, actions, and pages hosting. GitHub's own privacy policy applies.
- **OpenRouter** — LLM API calls for text extraction and drafting. Prompts sent to OpenRouter do not contain raw PII (only anonymised or encrypted references).
- **Listing sources** — property data is scraped from public listings. We do not transmit your data to listing sites.

## Data retention

Completed or aborted workflows are archived after 90 days. You may request immediate purge at any time by commenting `/abort` on your workflow issue, which overwrites all encrypted blocks with zeros and closes the issue.

## Your rights

You have the right to access, correct, or erase your data. Contact us via a GitHub issue or the email in our GitHub profile.
