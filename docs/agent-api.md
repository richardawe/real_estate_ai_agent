# Agent API

The agent API allows AI assistants (e.g. Claude, GPT) to manage real estate workflows on behalf of users. For MVP the API is document-only; the frontend talks directly to GitHub. A serverless function (Cloudflare Worker or Vercel) can implement these endpoints in future.

## Base URL

`https://api.realestateagent.example/v1` (not yet deployed; use GitHub API directly)

## Authentication

Bearer token from the user's GitHub OAuth device flow. All calls are scoped to `public_repo`.

## Endpoints

### POST /workflows

Start a new workflow.

```json
{
  "workflow_type": "buy",
  "intake_text": "I'm looking for a 3-bed house in Reading..."
}
```

Response: `{ "issue_number": 42, "workflow_id": "rwa-2026-042123" }`

Implementation: triggers `repository_dispatch` with event_type `intake_submitted`.

---

### GET /workflows/{issue_number}

Get current workflow state, front-matter, and pending HITL tasks.

Response: issue body (front-matter) + label list.

---

### POST /workflows/{issue_number}/commands

Post a slash-command as the authenticated user.

```json
{ "command": "/approve" }
```

Implementation: creates an issue comment via the GitHub API.

---

### GET /workflows/{issue_number}/comments

Get the workflow audit log (all issue comments).

---

## Error handling

All errors follow RFC 7807 Problem Details format:

```json
{
  "type": "https://realestateagent.example/errors/invalid-command",
  "title": "Unknown command",
  "detail": "/foo is not a recognised slash-command",
  "status": 400
}
```
