/**
 * Workflow live view — polls the GitHub Issues API every 15 seconds and
 * renders the workflow timeline, current state, pending HITL tasks, and
 * a progress stepper.
 */

import { gh } from './github-client.js';
import { renderHitlTask } from './task-renderer.js';

const POLL_INTERVAL_MS = 15_000;

const BUY_STEPS = ['intake','discover','shortlist_review','viewings','offer_draft','offer_submitted','due_diligence','closing','completed'];
const RENT_STEPS = ['intake','discover','shortlist_review','lease_review','closing','completed'];

const STEP_LABELS = {
  intake: 'Intake',
  discover: 'Searching',
  shortlist_review: 'Shortlist',
  viewings: 'Viewings',
  offer_draft: 'Offer draft',
  offer_submitted: 'Offer sent',
  due_diligence: 'Due diligence',
  lease_review: 'Lease review',
  closing: 'Closing',
  completed: 'Completed',
};

function parseYamlFrontMatter(body) {
  if (!body) return {};
  const match = body.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return {};
  const lines = match[1].split('\n');
  const result = {};
  let currentKey = null;
  for (const line of lines) {
    // List item: PyYAML block style uses no indent (- item) or 2-space indent (  - item)
    const listMatch = line.match(/^(?:  )?- (.+)$/);
    // Top-level key: value
    const kvMatch = line.match(/^(\w[\w_]+):\s*(.*)$/);
    if (listMatch && currentKey) {
      if (!Array.isArray(result[currentKey])) result[currentKey] = [];
      result[currentKey].push(listMatch[1].replace(/^['"]|['"]$/g, ''));
    } else if (kvMatch) {
      currentKey = kvMatch[1];
      const raw = kvMatch[2];
      if (raw === 'null') {
        result[currentKey] = null;
      } else if (raw.startsWith('[') && raw.endsWith(']')) {
        // Inline array: [] or [a, b, c]
        const inner = raw.slice(1, -1).trim();
        result[currentKey] = inner
          ? inner.split(',').map(s => s.trim().replace(/^['"]|['"]$/g, ''))
          : [];
      } else {
        result[currentKey] = raw;
      }
    }
  }
  return result;
}

function stateLabel(labels) {
  const s = labels.find(l => l.startsWith('state:'));
  return s ? s.replace('state:', '') : 'unknown';
}

function hitlKinds(labels) {
  return labels.filter(l => l.startsWith('hitl:')).map(l => l.replace('hitl:', ''));
}

function renderProgressSteps(state, workflowType) {
  const steps = workflowType === 'rent' ? RENT_STEPS : BUY_STEPS;
  const idx = steps.indexOf(state);
  const wrap = document.createElement('div');
  wrap.className = 'progress-steps';
  steps.forEach((step, i) => {
    const item = document.createElement('div');
    item.className = 'progress-step' +
      (i < idx ? ' progress-step--done' : i === idx ? ' progress-step--active' : '');
    item.innerHTML = `<span class="progress-dot"></span><span class="progress-label">${STEP_LABELS[step] || step}</span>`;
    wrap.appendChild(item);
    if (i < steps.length - 1) {
      const line = document.createElement('div');
      line.className = 'progress-line' + (i < idx ? ' progress-line--done' : '');
      wrap.appendChild(line);
    }
  });
  return wrap;
}

function renderMarkdown(md) {
  if (!md) return '';
  if (window.marked) {
    return window.marked.parse(md, { breaks: true });
  }
  // Fallback: basic rendering
  let out = md
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```[\w]*\n([\s\S]*?)\n?```/g, (_, c) => `<pre><code>${c}</code></pre>`)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^---$/gm, '<hr>')
    .replace(/\n\n+/g, '</p><p>')
    .replace(/\n/g, '<br>');
  return `<p>${out}</p>`;
}

function renderComment(comment) {
  const li = document.createElement('li');
  li.className = 'timeline-item';
  const isBot = comment.user.type === 'Bot' || comment.user.login.includes('[bot]');
  li.innerHTML = `
    <img class="timeline-avatar" src="${comment.user.avatar_url}" alt="${comment.user.login}" width="36" height="36" />
    <div class="timeline-body">
      <strong>${comment.user.login}</strong>${isBot ? ' <span class="agent-badge">agent</span>' : ''}
      <span style="color:#999;font-size:0.8em"> · ${new Date(comment.created_at).toLocaleString()}</span>
      <div class="comment-body md-content">${renderMarkdown(comment.body)}</div>
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
  const workflowType = fm.type || (labels.includes('flow:rent') ? 'rent' : 'buy');
  const pendingHitl = hitlKinds(labels);

  container.innerHTML = '';

  // Header with state badge and metadata
  const header = document.createElement('div');
  header.style.marginBottom = '1.5rem';
  header.innerHTML = `
    <span class="state-badge state-badge--${state.replace(/_/g,'')}">${state.replace(/_/g, ' ')}</span>
    <span style="color:#999;font-size:0.85em;margin-left:0.75rem">
      Workflow ${fm.workflow_id || ''} · ${workflowType} · ${fm.jurisdiction || ''}
    </span>
    <a href="https://github.com/${window._REPO}/issues/${issueNumber}" target="_blank" rel="noopener"
       style="font-size:0.8em;color:var(--brand);margin-left:1rem">GitHub issue →</a>
  `;
  container.appendChild(header);

  // Progress stepper
  container.appendChild(renderProgressSteps(state, workflowType));

  // Pending HITL tasks
  if (pendingHitl.length) {
    const tasksHeader = document.createElement('h3');
    tasksHeader.style.cssText = 'margin:1.5rem 0 0.5rem;color:#d68910';
    tasksHeader.textContent = 'Action required';
    container.appendChild(tasksHeader);
    for (const kind of pendingHitl) {
      const taskEl = renderHitlTask(kind, fm, issueNumber, comments);
      if (taskEl) container.appendChild(taskEl);
    }
  }

  // Timeline
  if (comments.length) {
    const timelineHeader = document.createElement('h3');
    timelineHeader.style.cssText = 'margin:1.5rem 0 0.5rem';
    timelineHeader.textContent = 'Activity';
    container.appendChild(timelineHeader);
  }
  const ul = document.createElement('ul');
  ul.className = 'timeline';
  for (const c of comments) {
    ul.appendChild(renderComment(c));
  }
  container.appendChild(ul);
}

export function initWorkflowView(repoName) {
  window._REPO = repoName;
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
      // Don't clear container on poll error — keep showing last good state
    }
  }

  poll();
  setInterval(poll, POLL_INTERVAL_MS);
}
