/**
 * GitHub API client using the OAuth device flow.
 *
 * The device flow lets the frontend authenticate without a backend server.
 * The token is stored in localStorage (disclosed in the privacy notice).
 *
 * Usage:
 *   import { GitHubClient, gh } from './github-client.js';
 *   const issue = await gh.getIssue(123);
 */

import { CONFIG } from '../config.js';

const TOKEN_KEY = 'rwa_gh_token';
const REPO = CONFIG.GITHUB_REPO;

export class GitHubClient {
  constructor({ repo = REPO, clientId } = {}) {
    this.repo = repo;
    this.clientId = clientId || CONFIG.GITHUB_OAUTH_CLIENT_ID;
    this.token = localStorage.getItem(TOKEN_KEY) || null;
  }

  get isAuthenticated() {
    return Boolean(this.token);
  }

  /**
   * Start the GitHub OAuth device flow. Returns { userCode, verificationUri }.
   * The caller should display these to the user and then call pollForToken().
   */
  async startDeviceFlow() {
    const resp = await fetch('https://github.com/login/device/code', {
      method: 'POST',
      headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: this.clientId, scope: 'public_repo' }),
    });
    const data = await resp.json();
    this._deviceCode = data.device_code;
    this._pollInterval = data.interval || 5;
    return {
      userCode: data.user_code,
      verificationUri: data.verification_uri,
    };
  }

  /**
   * Poll GitHub until the user completes the device flow authorisation.
   * Resolves when a token is obtained; rejects on expiry or error.
   */
  async pollForToken() {
    return new Promise((resolve, reject) => {
      const interval = setInterval(async () => {
        try {
          const resp = await fetch('https://github.com/login/oauth/access_token', {
            method: 'POST',
            headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
            body: JSON.stringify({
              client_id: this.clientId,
              device_code: this._deviceCode,
              grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
            }),
          });
          const data = await resp.json();
          if (data.access_token) {
            clearInterval(interval);
            this.token = data.access_token;
            localStorage.setItem(TOKEN_KEY, this.token);
            resolve(this.token);
          } else if (data.error === 'expired_token' || data.error === 'access_denied') {
            clearInterval(interval);
            reject(new Error(data.error));
          }
        } catch (err) {
          clearInterval(interval);
          reject(err);
        }
      }, this._pollInterval * 1000);
    });
  }

  signOut() {
    this.token = null;
    localStorage.removeItem(TOKEN_KEY);
  }

  async _fetch(path, options = {}) {
    const url = path.startsWith('https://') ? path : `https://api.github.com${path}`;
    const headers = {
      'Authorization': `Bearer ${this.token}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      ...options.headers,
    };
    const resp = await fetch(url, { ...options, headers });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`GitHub API ${resp.status}: ${text.slice(0, 200)}`);
    }
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
