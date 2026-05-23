/**
 * Supabase auth helpers.
 *
 * Exports a Supabase client and thin wrappers around email/password auth so
 * every page can import a single consistent instance.
 */

import { CONFIG } from '../config.js';

// Load Supabase from CDN — no build step required.
const { createClient } = await import(
  'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/esm/index.js'
);

export const supabase = createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_ANON_KEY);

/**
 * Create a new account with email + password.
 * @returns {Promise<{data, error}>}
 */
export async function signUp(email, password) {
  return supabase.auth.signUp({ email, password });
}

/**
 * Sign in with email + password.
 * @returns {Promise<{data, error}>}
 */
export async function signIn(email, password) {
  return supabase.auth.signInWithPassword({ email, password });
}

/**
 * Sign the current user out.
 * @returns {Promise<{error}>}
 */
export async function signOut() {
  return supabase.auth.signOut();
}

/**
 * Get the current session (null when not signed in).
 * @returns {Promise<Session|null>}
 */
export async function getSession() {
  const { data: { session } } = await supabase.auth.getSession();
  return session;
}

/**
 * Redirect to /login if there is no active session.
 * Saves the current page URL to sessionStorage so login.js can redirect back.
 */
export async function requireAuth() {
  const session = await getSession();
  if (!session) {
    sessionStorage.setItem('returnTo', location.href);
    location.href = '/login/';
  }
  return session;
}
