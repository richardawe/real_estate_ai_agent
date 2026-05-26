/**
 * Connectivity test Worker.
 *
 * GET /test?source=rightmove   — fetch a Rightmove search page and report what came back
 * GET /test?source=zoopla      — same for Zoopla
 *
 * Returns a JSON diagnostic so we know exactly what Cloudflare's edge sees.
 */

const TEST_URLS = {
  rightmove: "https://www.rightmove.co.uk/property-for-sale/find.html?locationIdentifier=REGION%5E274&maxPrice=400000&minBedrooms=3",
  zoopla: "https://www.zoopla.co.uk/for-sale/property/london/?price_max=400000&beds_min=3",
};

const BROWSER_HEADERS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "Accept-Language": "en-GB,en;q=0.9",
  "Accept-Encoding": "gzip, deflate, br",
  "Cache-Control": "no-cache",
};

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const source = url.searchParams.get("source") || "rightmove";
    const targetUrl = TEST_URLS[source];

    if (!targetUrl) {
      return Response.json({ error: `Unknown source: ${source}. Use rightmove or zoopla.` }, { status: 400 });
    }

    let resp;
    try {
      resp = await fetch(targetUrl, { headers: BROWSER_HEADERS });
    } catch (err) {
      return Response.json({ error: `Fetch failed: ${err.message}` }, { status: 500 });
    }

    const html = await resp.text();

    // Detect what kind of response we got
    const hasPropertyCards =
      html.includes("propertyCard") ||
      html.includes("property-card") ||
      html.includes("l-searchResult") ||
      html.includes("listing-results");

    const isChallenged =
      html.includes("cf-challenge") ||
      html.includes("Checking your browser") ||
      html.includes("challenge-platform") ||
      html.includes("turnstile") ||
      html.includes("captcha");

    const isErrorPage =
      html.includes("Access Denied") ||
      html.includes("403 Forbidden") ||
      html.includes("Rate limit");

    return Response.json({
      source,
      http_status: resp.status,
      content_length: html.length,
      verdict: hasPropertyCards
        ? "SUCCESS — real property listings received"
        : isChallenged
        ? "BLOCKED — bot challenge page returned"
        : isErrorPage
        ? "BLOCKED — error/access denied page"
        : "UNKNOWN — got HTML but no property cards detected",
      has_property_cards: hasPropertyCards,
      is_challenged: isChallenged,
      is_error_page: isErrorPage,
      // First 600 chars so we can see what the page actually is
      html_preview: html.slice(0, 600),
    });
  },
};
