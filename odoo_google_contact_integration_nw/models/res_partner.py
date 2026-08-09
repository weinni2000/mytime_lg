from odoo import _, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_import_google_contacts(self):
        """Import contacts using the active or sole configured company."""
        company = self.env.company
        required_fields = (
            company.contact_client_id,
            company.contact_client_secret,
            company.contact_company_refresh_token,
        )
        if not all(required_fields):
            configured_companies = self.env["res.company"].search(
                [
                    ("contact_client_id", "!=", False),
                    ("contact_client_secret", "!=", False),
                    ("contact_company_refresh_token", "!=", False),
                ]
            )
            if len(configured_companies) != 1:
                raise UserError(
                    _(
                        "Select a company with a configured Google Contacts "
                        "connection before importing contacts."
                    )
                )
            company = configured_companies
        return company.action_import_google_contacts()
