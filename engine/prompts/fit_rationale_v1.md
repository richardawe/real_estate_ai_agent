Write a property fit rationale for the shortlist.

Property details:
{property_json}

User requirements:
{requirements_json}

Eligibility result:
{eligibility_json}

Scoring:
{score_json}

Return JSON with:
- property_id: string (the property's external_id)
- headline: string (max 120 chars, why this property stands out)
- strengths: array of strings (what the property does well against requirements)
- weaknesses: array of strings (gaps or concerns, empty if none)
- fit_summary: string (max 400 chars, plain English paragraph)

Be factual. Only mention things present in the property details. Do not speculate.
Do not mention legal, financial, or investment advice.
