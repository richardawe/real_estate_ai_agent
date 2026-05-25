/**
 * Auth stub — the site uses a Fine-Grained PAT injected at build time.
 * No per-user sign-in is required; these exports are kept so pages that
 * call requireAuth() / getSession() continue to work unchanged.
 */

export function getSession() {
  return { configured: true };
}

export function signOut() {}

export async function requireAuth() {
  return { configured: true };
}
