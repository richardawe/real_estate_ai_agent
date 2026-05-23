# Adapter Authoring Guide

Adapters are YAML files that tell the runtime how to search a listing source, parse its results, and handle errors. Adding a new source means adding one YAML file — no Python changes needed for well-behaved sources.

## Listing adapter schema

```yaml
source_id: string          # Unique identifier (used in shortlist front-matter)
display_name: string       # Human-readable name
type: listings_search
runtime: playwright | http # playwright for JS-heavy sites, http for simple HTML
robots_check: true         # Always set true; the runtime will abort if disallowed
rate_limit_seconds: int    # Seconds to wait between page requests
auth: none | token         # Most public sources require no auth
jurisdiction: string       # e.g. "england", "us_ca"

search:
  base_url: string
  buy_url_template: string    # Template vars: {location_slug}, {budget_min}, {budget_max}, {bedrooms_min}
  rent_url_template: string   # Template vars: {location_slug}, {rent_min}, {rent_max}, {bedrooms_min}
  pagination:
    selector: string          # CSS selector for "next page" link (playwright)
    offset_param: string      # Query param name (http)
    offset_step: int
    max_pages: int

extract:
  card_selector: string      # CSS selector for a single listing card
  fields:
    <field_name>:
      selector: string       # CSS selector within the card
      attr: text | href | ...
      parse: currency_int | int_first | null   # Optional post-processor
      optional: true | false
      prefix: string         # Prepended to the extracted value (e.g. base URL for hrefs)

error_handling:
  abort_on_status: [403, 429]
  abort_action: post_warning_comment
  warning_message: string    # Supports {status_code}
```

## Offer form adapter schema

```yaml
form_id: string
display_name: string
jurisdiction: string
template_source: string    # URL of official template (gov.uk, state commission, etc.)
template_path: string      # Local path to the template markdown
required_fields: [list]
validations: [list]        # Deterministic checks (deposit cap, etc.)
human_review_required: true   # Always true
llm_may_draft_clauses: false  # Always false — LLM fills fields only
```

## Rules

1. Never set `robots_check: false`.
2. Set `rate_limit_seconds` to at least 2 for HTTP, 3 for Playwright.
3. `abort_on_status` must always include 403 and 429.
4. `llm_may_draft_clauses` must always be false on offer-form adapters.
5. Legal templates must come from official government or professional body sources. Never invent clauses.
