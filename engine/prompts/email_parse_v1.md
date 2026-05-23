Parse the following email from a seller or letting agent and extract a structured response.

Email content:
{email_text}

Return JSON with:
- decision: one of "accepted", "rejected", "countered"
- counter_price: integer or null (set only when decision is "countered")
- counter_notes: string or null (conditions or notes attached to a counter)
- conditions: array of strings (any conditions mentioned, e.g. "subject to survey")
- responding_party: string or null (name/role of who sent the email)

Rules:
- If the email accepts the offer unconditionally: decision = "accepted"
- If the email proposes a different price: decision = "countered", set counter_price
- If the email declines without a counter: decision = "rejected"
- Only extract what is explicitly stated. Do not infer or speculate.
