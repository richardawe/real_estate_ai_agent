Extract structured buying requirements from the following intake form submission.

Return JSON matching this schema exactly:
- full_name: string
- email: string (valid email)
- phone: string or null
- jurisdiction: string (e.g. "england", "us_ca")
- budget_min: integer (in local currency units, no commas)
- budget_max: integer (in local currency units)
- locations: array of strings (town/city names)
- bedrooms_min: integer (minimum 1)
- property_types: array of strings from ["house", "flat", "semi", "terraced", "bungalow", "any"]
- must_haves: array of strings (e.g. ["garden", "parking"])
- nice_to_haves: array of strings
- move_in_by: ISO date string (YYYY-MM-DD) or null
- gross_monthly_income: integer or null
- deposit_available: integer or null
- first_time_buyer: boolean

Rules:
- Convert written numbers ("three hundred thousand") to integers.
- If the user says "around £400k" treat it as budget_max=400000 and budget_min=350000 (10% below).
- If property_types is not mentioned, return [].
- If jurisdiction is not mentioned, infer from location names if possible, else return "unknown".
- Never fabricate information not present in the text.

Intake submission:
{intake_text}
