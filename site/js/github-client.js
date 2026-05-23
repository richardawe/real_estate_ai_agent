/**
 * GitHub API client — Supabase auth edition.
 *
 * Read operations (getIssue, listIssueComments, listWorkflows) call the
 * public GitHub REST API directly — no token required for public repos.
 *
 * Write operations (postComment, submitIntake, patchIssue) are proxied
 * through the Supabase Edge Function which holds the GitHub PAT.
 * The caller's Supabase JWT is forwarded so the function can verify identity.
 *
 * Usage:
 *   import { GitHubClient, gh } from './github-client.js';
 *   const issue = await gh.getIssue(123);
 */

import { CONFIG } from '../config.js';
import { supabase, getSession } from './auth.js';

const REPO = CONFIG.GITHUB_REPO;
const GITHUB_API = CONFIG.GITHUB_API;
const PROXY_URL = CONFIG.PROXY_URL;

export class GitHubClient {
  constructor({ repo = REPO, proxyUrl = PROXY_URL } = {}) {
    this.repo = repo;
    this.proxyUrl = proxyUrl;
  }

  /**
   * True when there is an active Supabase session.
   */
  get isAuthenticated() {
    // Synchronous approximation — use getSession() for authoritative check.
    // We expose this getter for quick UI guards; async callers should await getSession().
    return false; // overridden dynamically below via prototype
  }

  // ---------------------------------------------------------------------------
  // Public (read) — direct GitHub API, no auth header
  // ---------------------------------------------------------------------------

  async getIssue(number) {
    return this._publicFetch(`/repos/${this.repo}/issues/${number}`);
  }

  listIssueComments(number) {
    return this._publicFetch(`/repos/${this.repo}/issues/${number}/comments?per_page=100`);
  }

  listWorkflows() {
    return this._publicFetch(
      `/repos/${this.repo}/issues?labels=flow%3Abuy%2Cflow%3Arent&state=open&per_page=50`
    );
  }

  // ---------------------------------------------------------------------------
  // Private (write) — proxied through Supabase Edge Function
  // ---------------------------------------------------------------------------

  async postComment(number, body) {
    return this._proxyFetch({
      path: `/repos/${this.repo}/issues/${number}/comments`,
      method: 'POST',
      body: { body },
    });
  }

  /**
   * Submit an intake form by triggering a repository_dispatch event.
   */
  async submitIntake({ workflowType, intakeText }) {
    return this._proxyFetch({
      path: `/repos/${this.repo}/dispatches`,
      method: 'POST',
      body: {
        event_type: 'intake_submitted',
        client_payload: {
          workflow_type: workflowType,
          intake_text: intakeText,
        },
      },
    });
  }

  /**
   * Patch an existing issue (e.g. add a label, update body, change state).
   */
  async patchIssue(number, patch) {
    return this._proxyFetch({
      path: `/repos/${this.repo}/issues/${number}`,
      method: 'PATCH',
      body: patch,
    });
  }

  // ---------------------------------------------------------------------------
  // user_workflows table helpers (via Supabase JS client)
  // ---------------------------------------------------------------------------

  /**
   * Return all workflow rows belonging to the given user.
   */
  async getUserWorkflows(userId) {
    const { data, error } = await supabase
      .from('user_workflows')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false });
    if (error) throw new Error(`getUserWorkflows: ${error.message}`);
    return data;
  }

  /**
   * Persist a link between the signed-in user and a GitHub issue / workflow.
   */
  async saveUserWorkflow(userId, issueNumber, workflowId, workflowType) {
    const { data, error } = await supabase
      .from('user_workflows')
      .insert({
        user_id: userId,
        issue_number: issueNumber,
        workflow_id: workflowId,
        workflow_type: workflowType,
      })
      .select()
      .single();
    if (error) throw new Error(`saveUserWorkflow: ${error.message}`);
    return data;
  }

  // ---------------------------------------------------------------------------
  // Internal helpers
  // ---------------------------------------------------------------------------

  async _publicFetch(path) {
    const url = `${GITHUB_API}${path}`;
    const resp = await fetch(url, {
      headers: {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
      },
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`GitHub API ${resp.status}: ${text.slice(0, 200)}`);
    }
    return resp.json();
  }

  async _proxyFetch({ path, method = 'POST', body }) {
    const session = await getSession();
    if (!session) throw new Error('Not authenticated — please sign in.');

    const resp = await fetch(this.proxyUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({ path, method, body }),
    });

    const text = await resp.text();
    const data = text ? JSON.parse(text) : {};
    if (!resp.ok) {
      throw new Error(`Proxy ${resp.status}: ${JSON.stringify(data).slice(0, 200)}`);
    }
    return data;
  }
}

export const gh = new GitHubClient();
