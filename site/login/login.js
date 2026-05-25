/**
 * GitHub OAuth device flow handler.
 * Starts the device flow, shows the one-time code, polls for the token,
 * then redirects to the page that triggered the auth gate.
 */

import { getSession } from '../js/auth.js';
import { GitHubClient } from '../js/github-client.js';
import { CONFIG } from '../config.js';

// Already signed in — go straight to the return destination.
if (getSession()) {
  location.href = sessionStorage.getItem('returnTo') || CONFIG.BASE_PATH + '/';
}

const gh = new GitHubClient({ repo: CONFIG.GITHUB_REPO, clientId: CONFIG.GITHUB_OAUTH_CLIENT_ID });

const btn          = document.getElementById('signin-btn');
const codeBox      = document.getElementById('device-code-box');
const userCodeEl   = document.getElementById('user-code');
const verifyLink   = document.getElementById('verify-link');
const waitingHint  = document.getElementById('waiting-hint');
const errorEl      = document.getElementById('auth-error');

function showError(msg) {
  errorEl.textContent = msg;
  errorEl.classList.add('visible');
}

function hideError() {
  errorEl.classList.remove('visible');
}

btn.addEventListener('click', async () => {
  hideError();
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Starting…';

  try {
    const { userCode, verificationUri } = await gh.startDeviceFlow();

    userCodeEl.textContent = userCode;
    verifyLink.href = verificationUri;
    verifyLink.textContent = verificationUri.replace('https://', '');
    codeBox.style.display = 'block';

    btn.innerHTML = '<span class="spinner"></span> Waiting for authorisation…';
    waitingHint.textContent = 'Waiting for you to authorise…';

    await gh.pollForToken();

    // Token stored by pollForToken — redirect.
    waitingHint.textContent = 'Authorised! Redirecting…';
    location.href = sessionStorage.getItem('returnTo') || CONFIG.BASE_PATH + '/';
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = `
      <svg class="github-icon" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
          0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
          -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66
          .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
          -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0
          1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82
          1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01
          1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
      </svg>
      Sign in with GitHub`;
    codeBox.style.display = 'none';
    showError('Sign-in failed: ' + (err.message || 'unknown error') + '. Please try again.');
  }
});
