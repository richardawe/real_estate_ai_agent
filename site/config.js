/**
 * Site configuration.
 *
 * GITHUB_PAT: create a Fine-Grained PAT at github.com/settings/tokens
 *   → Fine-grained tokens → New token
 *   → "Only select repositories" → real_estate_ai_agent
 *   → Repository permissions:
 *       Issues      → Read and write
 *       Contents    → Read and write  (needed for repository_dispatch)
 *   Worst-case exposure: someone can post issues/comments on this repo.
 *
 * BASE_PATH: URL prefix where this site is served.
 *   GitHub project page:  "/real_estate_ai_agent"
 *   Custom domain / root: ""
 */
export const CONFIG = {
  GITHUB_PAT: "YOUR_FINE_GRAINED_PAT",
  GITHUB_REPO: "richardawe/real_estate_ai_agent",
  BASE_PATH: "/real_estate_ai_agent",
};
