/**
 * Auth helpers — GitHub OAuth token stored in localStorage.
 *
 * The token is obtained via the GitHub OAuth device flow on /login/.
 * No server, no external service — just a Fine-Grained PAT-equivalent
 * user token scoped to public_repo on this repo.
 */

const TOKEN_KEY = 'rwa_gh_token';

/** Returns { token } when signed in, null otherwise. */
export function getSession() {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { token } : null;
}

/** Remove the stored GitHub token (sign out). */
export function signOut() {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Redirect to /login/ if there is no active session.
 * Saves the current URL to sessionStorage so login.js can redirect back.
 */
export function requireAuth() {
  const session = getSession();
  if (!session) {
    sessionStorage.setItem('returnTo', location.href);
    location.href = '/login/';
  }
  return session;
}
