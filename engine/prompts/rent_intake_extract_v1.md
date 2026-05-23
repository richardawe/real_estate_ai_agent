Extract structured renting requirements from the following intake form submission.

Return JSON matching this schema exactly:
- full_name: string
- email: string (valid email)
- phone: string or null
- jurisdiction: string (e.g. "england", "us_ca")
- rent_min: integer (monthly, local currency, 0 if not stated)
- rent_max: integer (monthly, local currency)
- locations: array of strings
- bedrooms_min: integer
- property_types: array of strings from ["flat", "house", "studio", "room", "any"]
- must_haves: array of strings
- nice_to_haves: array of strings
- move_in_by: ISO date string or null
- gross_monthly_income: integer or null
- furnished_preference: "furnished" | "unfurnished" | "either" | null
- pets: boolean

Rules:
- If rent is stated as yearly, divide by 12 for monthly.
- If furnished preference is not mentioned, return null.
- Never fabricate information not present in the text.

Intake submission:
{intake_text}
