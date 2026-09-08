Uses the OpenAI key already configured for the `ai` module: the
`ai.openai_key` system parameter, or the `ODOO_AI_CHATGPT_TOKEN` environment
variable. No separate configuration is required.

Only products under the **All / Lisi Grün / Urproduktion / Blumen** category
(and its subcategories) are sent to ChatGPT as the known catalog, and are
considered when matching flowers to order lines. Adjust
`FLOWER_PRODUCT_CATEGORY_COMPLETE_NAME` in `models/_const.py` if the category
path differs.

A detected flower resolves to a product in this order: (1) the
**Sales > Configuration > Flower Name Mapping** table, matched by the exact
name ChatGPT used, (2) the database id ChatGPT returned directly from the
catalog it was given, (3) an `ilike` search by name within the flower
category. Use the **Sync Flower Mapping** button on the sale order to add
any newly-seen ChatGPT names to the mapping table (with a best-effort
product suggestion) for review/correction — future photos with the same
name will then resolve directly from the mapping table.

If none of the above resolves a product, a line is still added using a
default price instead: **Default Small Flower Price** or **Default Large
Flower Price** on the company record (Contacts > company > next to VAT),
depending on ChatGPT's size classification for that flower. These default
to 0.50 and 2.00 in the company currency and can be changed at any time.
