/**
 * Workflow live view — polls the GitHub Issues API every 15 seconds and
 * renders the workflow timeline, current state, and any pending HITL tasks.
 */

import { gh } from './github-client.js';
import { renderHitlTask } from './task-renderer.js';

const POLL_INTERVAL_MS = 15_000;

function parseYamlFrontMatter(body) {
  if (!body) return {};
  const match = body.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return {};
  // Minimal YAML parser for flat key: value and list structures.
  const lines = match[1].split('\n');
  const result = {};
  let currentKey = null;
  for (const line of lines) {
    const listMatch = line.match(/^  - (.+)$/);
    const kvMatch = line.match(/^(\w[\w_]+):\s*(.*)$/);
    if (listMatch && currentKey) {
      (result[currentKey] = result[currentKey] || []).push(listMatch[1]);
    } else if (kvMatch) {
      currentKey = kvMatch[1];
      result[currentKey] = kvMatch[2] === 'null' ? null : kvMatch[2];
    }
  }
  return result;
}

function stateLabel(labels) {
  const state = labels.find(l => l.startsWith('state:'));
  return state ? state.replace('state:', '') : 'unknown';
}

function hitlKinds(labels) {
  return labels.filter(l => l.startsWith('hitl:')).map(l => l.replace('hitl:', ''));
}

function renderComment(comment) {
  const li = document.createElement('li');
  li.className = 'timeline-item';
  li.innerHTML = `
    <img class="timeline-avatar" src="${comment.user.avatar_url}" alt="${comment.user.login}" width="36" height="36" />
    <div class="timeline-body">
      <strong>${comment.user.login}</strong>
      <span style="color:#999;font-size:0.8em"> · ${new Date(comment.created_at).toLocaleString()}</span>
      <div class="comment-body">${comment.body.replace(/\n/g, '<br>')}</div>
    </div>
  `;
  return li;
}

async function loadAndRender(issueNumber, container) {
  const [issue, comments] = await Promise.all([
    gh.getIssue(issueNumber),
    gh.listIssueComments(issueNumber),
  ]);

  const labels = (issue.labels || []).map(l => l.name);
  const fm = parseYamlFrontMatter(issue.body);
  const state = stateLabel(labels);
  const pendingHitl = hitlKinds(labels);

  container.innerHTML = `
    <div style="margin-bottom:1.5rem">
      <span class="state-badge">${state.replace(/_/g, ' ')}</span>
      <span style="color:#999;font-size:0.85em;margin-left:0.75rem">
        Workflow ${fm.workflow_id || ''} · ${fm.type || ''} · ${fm.jurisdiction || ''}
      </span>
    </div>
  `;

  // Render pending HITL tasks.
  for (const kind of pendingHitl) {
    const taskEl = renderHitlTask(kind, fm, issueNumber);
    if (taskEl) container.appendChild(taskEl);
  }

  // Timeline.
  const ul = document.createElement('ul');
  ul.className = 'timeline';
  for (const c of comments) {
    ul.appendChild(renderComment(c));
  }
  container.appendChild(ul);
}

export function initWorkflowView() {
  const params = new URLSearchParams(location.search);
  const issueNumber = params.get('id');
  if (!issueNumber) {
    document.getElementById('workflow-container').textContent = 'No workflow ID specified.';
    return;
  }

  const container = document.getElementById('workflow-container');

  async function poll() {
    try {
      await loadAndRender(parseInt(issueNumber), container);
    } catch (err) {
      console.error('Poll error:', err);
    }
  }

  poll();
  setInterval(poll, POLL_INTERVAL_MS);
}
