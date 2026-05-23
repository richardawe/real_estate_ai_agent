/**
 * Site configuration.
 * SUPABASE_URL and SUPABASE_ANON_KEY are safe to commit — they are public values.
 * Secrets (GitHub PAT) live only in the Supabase Edge Function environment.
 */
export const CONFIG = {
  SUPABASE_URL: "YOUR_SUPABASE_PROJECT_URL",      // e.g. https://xyzxyz.supabase.co
  SUPABASE_ANON_KEY: "YOUR_SUPABASE_ANON_KEY",   // safe to commit
  GITHUB_REPO: "richardawe/real_estate_ai_agent",
  GITHUB_API: "https://api.github.com",
  PROXY_URL: "YOUR_SUPABASE_PROJECT_URL/functions/v1/github-proxy",
};
