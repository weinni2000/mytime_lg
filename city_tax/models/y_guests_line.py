from odoo import api, fields, models

_MAIN_GUEST_CHECK_SELECTION = [("na", "NA"), ("ok", "OK"), ("invalid", "Invalid")]


class YGuestsLine(models.Model):
    _name = "y_guests_line"
    _description = "Guests Line"

    x_sequence = fields.Integer(string="Sequence", copy=True)
    x_name = fields.Char(string="Description")
    x_sale_order_id = fields.Many2one("sale.order", string="Sale Order")
    x_guest_partner_id = fields.Many2one("res.partner", string="Guest", copy=True)
    x_room_resource_id = fields.Many2one("resource.resource", string="Room")
    x_sol_resource_ids = fields.Many2many("resource.resource", string="Resource IDs")
    x_guest_identity_check = fields.Selection(
        related="x_guest_partner_id.x_identity_check", string="Identity Check", readonly=True
    )

    x_main_guest = fields.Boolean(string="Main Guest", copy=True)
    x_refresh = fields.Boolean(
        string="Refresh", help="Toggle to force the arrival/departure and guest-check fields to recompute."
    )
    x_arrival_date = fields.Date(string="Arrival", compute="_compute_x_arrival_date", store=True)
    x_arrival_date_manual = fields.Date(
        string="Arrival (Manual)",
        help="Overrides the sale order's rental start date when set, e.g. for "
        "guests not attached to any order (imported from a sheet, ...).",
    )
    x_planned_departure_date = fields.Date(string="Planned Departure")
    x_departure_date = fields.Date(string="Departure", compute="_compute_x_departure_date", store=True)
    x_departure_date_manual = fields.Date(
        string="Departure (Manual)",
        help="Overrides the sale order's rental return date when set, e.g. for "
        "guests not attached to any order (imported from a sheet, ...).",
    )
    x_save_as_contact = fields.Boolean(string="Save In Guest Addresses", default=True)

    x_guest_name = fields.Char(related="x_guest_partner_id.name", store=True, readonly=False)
    x_guest_title_id = fields.Many2one(
        "res.partner.title", related="x_guest_partner_id.title_id", store=True, readonly=False
    )
    x_anrede = fields.Selection(related="x_guest_partner_id.x_anrede", store=True, readonly=False)
    x_guest_lang = fields.Selection(related="x_guest_partner_id.lang", store=True, readonly=False)
    x_guest_country_id = fields.Many2one(
        "res.country", related="x_guest_partner_id.country_id", store=True, readonly=False
    )
    x_guest_nationality = fields.Many2one(
        "res.country", related="x_guest_partner_id.x_nationality", store=True, readonly=False
    )
    x_calc_nationality_id = fields.Many2one(
        "res.country", related="x_guest_partner_id.x_calc_nationality_id", readonly=True
    )
    x_guest_zip = fields.Char(related="x_guest_partner_id.zip", store=True, readonly=False)
    x_guest_city = fields.Char(related="x_guest_partner_id.city", store=True, readonly=False)
    x_guest_street = fields.Char(related="x_guest_partner_id.street", store=True, readonly=False)
    x_guest_document_type = fields.Selection(
        related="x_guest_partner_id.x_document_type", store=True, readonly=False
    )
    x_guest_document_number = fields.Char(
        related="x_guest_partner_id.x_document_number", store=True, readonly=False
    )
    x_guest_document_date = fields.Date(related="x_guest_partner_id.x_document_date", store=True, readonly=False)
    x_guest_document_authority = fields.Char(
        related="x_guest_partner_id.x_document_authority", store=True, readonly=False
    )
    x_guest_birthdate = fields.Date(related="x_guest_partner_id.x_birthdate", store=True, readonly=False)
    x_guest_age = fields.Integer(related="x_guest_partner_id.x_age", readonly=True)
    x_guest_marketing_consent = fields.Boolean(
        related="x_guest_partner_id.x_marketing_consent", store=True, readonly=False
    )

    x_main_guest_check = fields.Selection(
        _MAIN_GUEST_CHECK_SELECTION, string="Guest Check", compute="_compute_x_main_guest_check"
    )
    x_guest_check_warning = fields.Char(string="Guest Check Warning", compute="_compute_x_main_guest_check")
    x_group_id = fields.Many2one(
        "guest.tax.message",
        string="Grouping",
        copy=False,
        readonly=True,
        help="The sale order this guest belongs to, or a standalone grouping "
        "for guests not attached to any order.",
    )

    def _compute_display_name(self):
        for guest_line in self:
            parts = [part for part in (guest_line.x_guest_name, guest_line.x_name) if part]
            guest_line.display_name = " - ".join(parts) if parts else self.env._("Guest Line")

    @api.model_create_multi
    def create(self, vals_list):
        guest_tax_message = self.env["guest.tax.message"]
        for vals in vals_list:
            if vals.get("x_group_id"):
                continue
            sale_order_id = vals.get("x_sale_order_id")
            if sale_order_id:
                order = self.env["sale.order"].browse(sale_order_id)
                vals["x_group_id"] = guest_tax_message._get_or_create_for_sale_order(order).id
            else:
                vals["x_group_id"] = guest_tax_message._create_standalone().id
        return super().create(vals_list)

    @api.depends(
        "x_refresh",
        "x_arrival_date_manual",
        "x_group_id.x_arrival_date",
        "x_sale_order_id.rental_start_date",
    )
    def _compute_x_arrival_date(self):
        for guest_line in self:
            if guest_line.x_arrival_date_manual:
                guest_line.x_arrival_date = guest_line.x_arrival_date_manual
            elif guest_line.x_group_id.x_arrival_date:
                guest_line.x_arrival_date = guest_line.x_group_id.x_arrival_date
            else:
                start = guest_line.x_sale_order_id.rental_start_date
                guest_line.x_arrival_date = start.date() if start else False

    @api.depends(
        "x_refresh",
        "x_departure_date_manual",
        "x_group_id.x_departure_date",
        "x_sale_order_id.rental_return_date",
    )
    def _compute_x_departure_date(self):
        for guest_line in self:
            if guest_line.x_departure_date_manual:
                guest_line.x_departure_date = guest_line.x_departure_date_manual
            elif guest_line.x_group_id.x_departure_date:
                guest_line.x_departure_date = guest_line.x_group_id.x_departure_date
            else:
                end = guest_line.x_sale_order_id.rental_return_date
                guest_line.x_departure_date = end.date() if end else False

    @api.depends(
        "x_main_guest",
        "x_refresh",
        "x_arrival_date",
        "x_departure_date",
        "x_guest_partner_id.x_guest_data_check",
        "x_guest_partner_id.x_guest_full_data_check",
    )
    def _compute_x_main_guest_check(self):
        for guest_line in self:
            if not guest_line.x_guest_partner_id:
                guest_line.x_main_guest_check = "na"
                guest_line.x_guest_check_warning = False
                continue
            if not guest_line.x_main_guest:
                guest_line.x_main_guest_check = guest_line.x_guest_partner_id.x_guest_data_check
                guest_line.x_guest_check_warning = guest_line.x_guest_partner_id.x_guest_data_warning
                continue
            missing = []
            if not guest_line.x_arrival_date:
                missing.append("Arrival")
            if not guest_line.x_departure_date:
                missing.append("Departure")
            partner_warning = guest_line.x_guest_partner_id.x_guest_full_data_warning
            if partner_warning:
                missing.append(partner_warning.replace("Missing: ", ""))
            if missing:
                guest_line.x_main_guest_check = "invalid"
                guest_line.x_guest_check_warning = "Missing: " + ", ".join(missing)
            else:
                guest_line.x_main_guest_check = "ok"
                guest_line.x_guest_check_warning = False
