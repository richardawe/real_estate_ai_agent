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

// Expose globally for inline onclick handlers
window._postSlashCommand = postSlashCommand;

function makeCard(title, innerHTML) {
  const card = document.createElement('div');
  card.className = 'hitl-card';
  card.innerHTML = `<h3>${title}</h3>${innerHTML}`;
  return card;
}

function btn(text, cls, cmd, issueNumber) {
  return `<button class="btn ${cls}" onclick="window._postSlashCommand(${issueNumber}, '${cmd}')">${text}</button>`;
}

// ---------------------------------------------------------------------------
// Shortlist table parser
// ---------------------------------------------------------------------------

function parseShortlistFromComments(comments) {
  for (const c of (comments || [])) {
    if (!c.body || !c.body.includes('| # | Address |')) continue;
    const lines = c.body.split('\n').filter(l => l.startsWith('|'));
    const dataLines = lines.filter(l => !l.match(/^[|\s:-]+$/)).slice(1); // skip header
    return dataLines.map(line => {
      const cells = line.split('|').slice(1, -1).map(c => c.trim());
      // columns: #, Address, Price, Beds, Score, Link, ID
      const linkMatch = cells[5] && cells[5].match(/\[([^\]]+)\]\(([^)]+)\)/);
      const idMatch = cells[6] && cells[6].match(/`([^`]+)`/);
      return {
        num: cells[0] || '',
        address: cells[1] || '',
        price: cells[2] || '',
        beds: cells[3] || '?',
        url: linkMatch ? linkMatch[2] : null,
        id: idMatch ? idMatch[1] : (cells[6] || ''),
      };
    }).filter(p => p.id);
  }
  return [];
}

// ---------------------------------------------------------------------------
// Renderers
// ---------------------------------------------------------------------------

function renderReviewShortlist(fm, issueNumber, comments) {
  const properties = parseShortlistFromComments(comments);
  const liked = Array.isArray(fm.liked) ? fm.liked : [];

  window._postCmd = (cmd, num) => postSlashCommand(num, cmd);

  let tableHtml;
  if (properties.length) {
    const rows = properties.map(p => {
      const isLiked = liked.includes(p.id);
      const linkHtml = p.url
        ? `<a href="${p.url}" target="_blank" rel="noopener" style="color:var(--brand)">View →</a>`
        : '—';
      const likeBtn = `<button class="btn btn--approve" style="padding:.25rem .6rem;font-size:.8rem"
        onclick="window._postCmd('/like ${p.id}', ${issueNumber})">${isLiked ? '♥ Liked' : 'Like'}</button>`;
      const skipBtn = `<button class="btn btn--reject" style="padding:.25rem .6rem;font-size:.8rem;margin-left:.3rem"
        onclick="window._postCmd('/skip ${p.id}', ${issueNumber})">Skip</button>`;
      return `<tr${isLiked ? ' style="background:#f0fff4"' : ''}>
        <td>${p.address}</td><td>${p.price}</td><td>${p.beds}</td>
        <td>${linkHtml}</td><td style="white-space:nowrap">${likeBtn}${skipBtn}</td>
      </tr>`;
    }).join('');
    tableHtml = `<table class="property-table">
      <thead><tr><th>Address</th><th>Price</th><th>Beds</th><th>Link</th><th>Action</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  } else if (Array.isArray(fm.shortlist) && fm.shortlist.length) {
    // Fallback to IDs only
    const rows = fm.shortlist.map(id => {
      const isLiked = liked.includes(id);
      return `<tr${isLiked ? ' style="background:#f0fff4"' : ''}>
        <td><code>${id}</code></td>
        <td style="white-space:nowrap">
          <button class="btn btn--approve" style="padding:.25rem .6rem;font-size:.8rem"
            onclick="window._postCmd('/like ${id}', ${issueNumber})">${isLiked ? '♥ Liked' : 'Like'}</button>
          <button class="btn btn--reject" style="padding:.25rem .6rem;font-size:.8rem;margin-left:.3rem"
            onclick="window._postCmd('/skip ${id}', ${issueNumber})">Skip</button>
        </td>
      </tr>`;
    }).join('');
    tableHtml = `<table class="property-table">
      <thead><tr><th>Property ID</th><th>Action</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  } else {
    return makeCard('Review shortlist', '<p>The shortlist is being prepared — check back in a few minutes.</p>');
  }

  const likedCount = liked.length;
  const approveBar = likedCount > 0
    ? `<div class="liked-bar">
        <strong>${likedCount} property${likedCount > 1 ? 'ies' : ''} liked</strong>
        — click Approve to get viewing contact templates.
        <button class="btn btn--approve" style="margin-left:1rem"
          onclick="window._postCmd('/approve', ${issueNumber})">✓ Approve shortlist</button>
      </div>`
    : `<div class="liked-bar liked-bar--hint">
        Like at least one property above, then click <strong>Approve shortlist</strong>.
      </div>`;

  return makeCard('Review your shortlist', `
    <p>Like the properties you want to pursue — then approve the shortlist to receive viewing request templates.</p>
    ${tableHtml}
    ${approveBar}
  `);
}

function renderApproveOffer(fm, issueNumber) {
  const tx = fm.current_transaction;
  const detailHtml = tx && typeof tx === 'object'
    ? `<ul style="margin:.5rem 0 .5rem 1.25rem">
        ${tx.property_address ? `<li><strong>Property:</strong> ${tx.property_address}</li>` : ''}
        ${tx.amount ? `<li><strong>Offer price:</strong> £${Number(tx.amount).toLocaleString()}</li>` : ''}
      </ul>`
    : '';
  const card = makeCard('Approve offer draft', `
    ${detailHtml}
    <p>An offer draft is ready in the latest agent comment above. Review it carefully.</p>
    <p>To request changes: reply <code>/note &lt;what to change&gt;</code> and I'll redraft.</p>
    <div style="margin-top:1rem;display:flex;gap:.75rem">
      ${btn('✓ Approve & get submission package', 'btn--approve', '/approve', issueNumber)}
      ${btn('✗ Reject', 'btn--reject', '/reject', issueNumber)}
    </div>
  `);
  return card;
}

function renderApproveViewing(fm, issueNumber) {
  const card = makeCard('Approve viewing request', `
    <p>Viewing request drafts are ready in the latest agent comment. Check the suggested times.</p>
    <p>To adjust availability: reply <code>/note &lt;your availability&gt;</code> before approving.</p>
    <div style="margin-top:1rem;display:flex;gap:.75rem">
      ${btn('✓ Approve', 'btn--approve', '/approve', issueNumber)}
      ${btn('✗ Reject', 'btn--reject', '/reject', issueNumber)}
    </div>
  `);
  return card;
}

function renderCounterDecision(fm, issueNumber) {
  const card = makeCard('Respond to counter-offer', `
    <p>The seller has countered. Choose your response:</p>
    <div style="display:flex;gap:.75rem;flex-wrap:wrap;margin-top:1rem">
      ${btn('Accept counter', 'btn--approve', '/approve', issueNumber)}
      ${btn('Reject', 'btn--reject', '/reject', issueNumber)}
    </div>
    <div style="margin-top:1rem">
      <label style="font-weight:600;display:block;margin-bottom:.4rem">Or submit your own counter:</label>
      <input id="counter-input" type="number" placeholder="Amount (e.g. 395000)"
        style="padding:.5rem;border:1px solid #ccc;border-radius:6px;width:200px" />
      <button class="btn btn--counter" style="margin-left:.5rem"
        onclick="window._postSlashCommand(${issueNumber}, '/counter ' + document.getElementById('counter-input').value)">
        Counter →
      </button>
    </div>
  `);
  return card;
}

function renderLeaseReview(fm, issueNumber) {
  const card = makeCard('Review lease', `
    <p>A lease summary is ready in the latest agent comment above. Read it carefully and have your solicitor review the full document before approving.</p>
    <p><strong>Warning:</strong> approving will move to the closing step. Do not approve until you are satisfied with all terms.</p>
    <div style="margin-top:1rem;display:flex;gap:.75rem">
      ${btn('✓ Approve lease', 'btn--approve', '/approve', issueNumber)}
      ${btn('✗ Reject', 'btn--reject', '/reject', issueNumber)}
    </div>
  `);
  return card;
}

function renderPaymentConfirmation(fm, issueNumber) {
  return makeCard('Payment confirmation', `
    <p>Upload a screenshot of your payment receipt as an issue attachment, then confirm below.</p>
    <button class="btn btn--approve" style="margin-top:1rem"
      onclick="window._postSlashCommand(${issueNumber}, '/approve')">
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

export function renderHitlTask(kind, fm, issueNumber, comments = []) {
  const renderer = RENDERERS[kind];
  return renderer ? renderer(fm, issueNumber, comments) : null;
}
