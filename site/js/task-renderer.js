/**
 * HITL task renderers.
 *
 * Maps hitl:<kind> label → a DOM element the user can interact with.
 * Each renderer returns an HTMLElement or null if the kind is unknown.
 * All actions post a slash-command comment to the issue via the GitHub client.
 */

import { gh } from './github-client.js';

async function postSlashCommand(issueNumber, command) {
  try {
    await gh.postComment(issueNumber, command);
    window.location.reload();
  } catch (err) {
    alert(`Failed to post command: ${err.message}`);
  }
}

function makeCard(title, innerHTML) {
  const card = document.createElement('div');
  card.className = 'hitl-card';
  card.innerHTML = `<h3>${title}</h3>${innerHTML}`;
  return card;
}

function approveRejectButtons(issueNumber, approveCmd = '/approve', rejectCmd = '/reject') {
  const wrap = document.createElement('div');
  wrap.style.marginTop = '1rem';
  wrap.style.display = 'flex';
  wrap.style.gap = '0.75rem';

  const approveBtn = document.createElement('button');
  approveBtn.className = 'btn btn--approve';
  approveBtn.textContent = '✓ Approve';
  approveBtn.onclick = () => postSlashCommand(issueNumber, approveCmd);

  const rejectBtn = document.createElement('button');
  rejectBtn.className = 'btn btn--reject';
  rejectBtn.textContent = '✗ Reject';
  rejectBtn.onclick = () => postSlashCommand(issueNumber, rejectCmd);

  wrap.append(approveBtn, rejectBtn);
  return wrap;
}

// ---------------------------------------------------------------------------
// Renderers
// ---------------------------------------------------------------------------

function renderReviewShortlist(fm, issueNumber) {
  const shortlist = fm.shortlist || [];
  if (!Array.isArray(shortlist) || !shortlist.length) {
    return makeCard(
      'Review shortlist',
      '<p>The shortlist is being prepared. Refresh in a few minutes.</p>'
    );
  }

  const rows = shortlist.map(id => `
    <tr>
      <td><code>${id}</code></td>
      <td>
        <button class="btn btn--approve" style="padding:0.3rem 0.75rem;font-size:0.8rem"
          onclick="postCmd('/like ${id}', ${issueNumber})">Like</button>
        <button class="btn btn--reject" style="padding:0.3rem 0.75rem;font-size:0.8rem;margin-left:0.4rem"
          onclick="postCmd('/skip ${id}', ${issueNumber})">Skip</button>
      </td>
    </tr>
  `).join('');

  const card = makeCard('Review your shortlist', `
    <p>React to each property below, then the agent will arrange viewings.</p>
    <table class="property-table">
      <thead><tr><th>Property ID</th><th>Action</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `);

  // Expose helper for inline onclick.
  window.postCmd = (cmd, num) => postSlashCommand(num, cmd);
  return card;
}

function renderApproveOffer(fm, issueNumber) {
  const card = makeCard('Approve offer draft', `
    <p>
      An offer has been drafted for your review. Check the latest agent comment
      above for the full draft text.
    </p>
    <p>To request changes before approving, reply with:
      <code>/note &lt;what to change&gt;</code>
    </p>
  `);
  card.appendChild(approveRejectButtons(issueNumber));
  return card;
}

function renderApproveViewing(fm, issueNumber) {
  const card = makeCard('Approve viewing request', `
    <p>
      Viewing requests have been drafted. Check the latest agent comment for
      the suggested times. Reply <code>/note &lt;your availability&gt;</code>
      to adjust times before approving.
    </p>
  `);
  card.appendChild(approveRejectButtons(issueNumber));
  return card;
}

function renderCounterDecision(fm, issueNumber) {
  const card = makeCard('Respond to counter-offer', `
    <p>The seller has countered. Choose your response:</p>
    <div style="display:flex;gap:0.75rem;flex-wrap:wrap;margin-top:1rem">
      <button class="btn btn--approve"
        onclick="postSlashCommand(${issueNumber}, '/approve')">Accept counter</button>
      <button class="btn btn--reject"
        onclick="postSlashCommand(${issueNumber}, '/reject')">Reject</button>
    </div>
    <div style="margin-top:1rem">
      <label style="font-weight:600;display:block;margin-bottom:0.4rem">
        Or submit your own counter:
      </label>
      <input id="counter-input" type="number" placeholder="Amount"
        style="padding:0.5rem;border:1px solid #ccc;border-radius:6px;width:180px" />
      <button class="btn btn--counter" style="margin-left:0.5rem"
        onclick="postSlashCommand(${issueNumber}, '/counter ' + document.getElementById('counter-input').value)">
        Counter →
      </button>
    </div>
  `);
  window.postSlashCommand = postSlashCommand;
  return card;
}

function renderLeaseReview(fm, issueNumber) {
  const card = makeCard('Review lease', `
    <p>
      A lease draft is ready for your review. Check the latest agent comment
      for the redline diff. Have your solicitor review before approving.
    </p>
    <p>
      <strong>Warning:</strong> approving will move to the e-sign step.
      Do not approve until you are satisfied with all terms.
    </p>
  `);
  card.appendChild(approveRejectButtons(issueNumber));
  return card;
}

function renderPaymentConfirmation(fm, issueNumber) {
  return makeCard('Payment confirmation', `
    <p>
      Upload a screenshot of your payment receipt as an issue attachment,
      then comment <code>/approve</code> to confirm.
    </p>
    <button class="btn btn--approve" style="margin-top:1rem"
      onclick="postSlashCommand(${issueNumber}, '/approve')">
      Confirm payment →
    </button>
  `);
}

// ---------------------------------------------------------------------------
// Dispatch
// ---------------------------------------------------------------------------

const RENDERERS = {
  review_shortlist: renderReviewShortlist,
  approve_offer: renderApproveOffer,
  approve_viewing: renderApproveViewing,
  counter_decision: renderCounterDecision,
  lease_review: renderLeaseReview,
  payment_confirmation: renderPaymentConfirmation,
};

export function renderHitlTask(kind, fm, issueNumber) {
  const renderer = RENDERERS[kind];
  return renderer ? renderer(fm, issueNumber) : null;
}
