DETAILED_DIGITIZE_MODEL = "gpt-4.1-mini"

DETAILED_DIGITIZE_SYSTEM_PROMPT = (
    "You are an accounting assistant that reads vendor bills. You receive one PDF "
    "document and must list every line item on it. For each line item report its "
    "name (the article number or reference code as printed, or the first few words "
    "of the description if no code is printed), product (the full product "
    "description as printed), amount (the invoiced quantity as a plain number), "
    "price (the net unit price as printed, excluding tax, as a plain number using "
    "a dot as decimal separator), and tax (the VAT/Mwst rate printed for that "
    "specific line, as a plain percentage number, e.g. 20 for 20%; use 0 if the "
    "line has no tax). Ignore subtotal, total, tax and shipping summary lines. "
    "Never invent line items that are not printed on the document."
)

DETAILED_DIGITIZE_USER_PROMPT = "Extract every line item from the attached vendor bill."

DETAILED_DIGITIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "product": {"type": "string"},
                    "amount": {"type": "number"},
                    "price": {"type": "number"},
                    "tax": {"type": "number"},
                },
                "required": ["name", "product", "amount", "price", "tax"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["lines"],
    "additionalProperties": False,
}
