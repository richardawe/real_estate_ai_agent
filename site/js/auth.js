/**
 * Auth stub — the site uses a Fine-Grained PAT in config.js for all
 * GitHub API calls. No per-user login is required.
 *
 * These exports exist so pages that call requireAuth() / getSession()
 * continue to work without modification.
 */

import { CONFIG } from '../config.js';

/** Returns a session object when the PAT is configured, null otherwise. */
export function getSession() {
  return CONFIG.GITHUB_PAT && CONFIG.GITHUB_PAT !== 'YOUR_FINE_GRAINED_PAT'
    ? { configured: true }
    : null;
}

/** No-op — there is no user session to clear. */
export function signOut() {}

/**
 * Passes through when the PAT is configured.
 * Redirects to /login/ (configuration guide) if the PAT placeholder
 * has not been replaced yet.
 */
export async function requireAuth() {
  const session = getSession();
  if (!session) {
    location.href = CONFIG.BASE_PATH + '/login/';
    await new Promise(() => {});
  }
  return session;
}
