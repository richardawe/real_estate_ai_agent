/**
 * GitHub API client — PAT edition.
 *
 * Uses a Fine-Grained PAT stored in config.js for all API calls.
 * Read operations (public repo) don't strictly need auth, but using
 * the PAT avoids rate-limit issues.
 *
 * Usage:
 *   import { gh } from './github-client.js';
 *   const issue = await gh.getIssue(123);
 */

import { CONFIG } from '../config.js';

const REPO = CONFIG.GITHUB_REPO;

export class GitHubClient {
  constructor({ repo = REPO } = {}) {
    this.repo = repo;
  }

  async _fetch(path, options = {}) {
    const url = path.startsWith('https://') ? path : `https://api.github.com${path}`;
    const headers = {
      'Authorization': `Bearer ${CONFIG.GITHUB_PAT}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      ...options.headers,
    };
    const resp = await fetch(url, { ...options, headers });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`GitHub API ${resp.status}: ${text.slice(0, 200)}`);
    }
    if (resp.status === 204) return {};
    return resp.json();
  }

  getIssue(number) {
    return this._fetch(`/repos/${this.repo}/issues/${number}`);
  }

  listIssueComments(number) {
    return this._fetch(`/repos/${this.repo}/issues/${number}/comments?per_page=100`);
  }

  listWorkflows() {
    return this._fetch(`/repos/${this.repo}/issues?labels=flow:buy,flow:rent&state=open&per_page=50`);
  }

  postComment(number, body) {
    return this._fetch(`/repos/${this.repo}/issues/${number}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body }),
    });
  }

  async submitIntake({ workflowType, intakeText }) {
    await this._fetch(`/repos/${this.repo}/dispatches`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_type: 'intake_submitted',
        client_payload: {
          workflow_type: workflowType,
          intake_text: intakeText,
        },
      }),
    });
  }

  patchIssue(number, patch) {
    return this._fetch(`/repos/${this.repo}/issues/${number}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
  }
}

export const gh = new GitHubClient();
