_COMPANY_NAME = "Camping@LisiGrün"

_DESKLINE_SETTINGS = {
    "x_deskline_property_id": "04b8e48f-64fd-420b-8bbb-7d0c25167aff",
    "x_deskline_db_ov": "MW9",
}


def post_init_hook(env):
    company = env["res.company"].search([("name", "=", _COMPANY_NAME)], limit=1)
    if company:
        company.write(_DESKLINE_SETTINGS)
