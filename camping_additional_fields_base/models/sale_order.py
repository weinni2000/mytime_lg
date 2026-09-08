from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    special_temporary_info = fields.Text(
        related="company_id.special_temporary_info",
        string="Special Temporary Information",
        readonly=True,
    )
    directions = fields.Text(
        compute="_compute_direction_info",
    )
    direction_product_template_ids = fields.Many2many(
        comodel_name="product.template",
        compute="_compute_direction_info",
    )
    is_paid = fields.Boolean(
        string="Paid",
        compute="_compute_is_paid",
        store=True,
    )
    city_tax_left = fields.Monetary(
        currency_field="currency_id",
    )
    is_ongoing = fields.Boolean(
        string="Ongoing",
        compute="_compute_is_ongoing",
        store=True,
    )
    ota_payment = fields.Boolean(
        related="sale_channel_id.ota_payment",
        string="OTA Payment",
        store=True,
    )
    planning_role_ids = fields.Many2many(
        comodel_name="planning.role",
        string="Planning Roles",
        compute="_compute_planning_role_ids",
        store=True,
    )
    amount_guests = fields.Integer(
        string="Guests",
        compute="_compute_amount_guests",
        store=True,
    )
    calc_payment_type = fields.Selection(
        selection=[
            ("cash", "Cash"),
            ("banktransfer", "Bank Transfer"),
            ("verrechnungskonto", "Verrechnungskonto"),
        ],
        string="Payment Type",
        compute="_compute_calc_payment_type",
        store=True,
    )

    @api.depends("x_guest_line_ids")
    def _compute_amount_guests(self):
        for order in self:
            order.amount_guests = len(order.x_guest_line_ids)

    @api.depends("invoice_ids.payment_state", "invoice_ids.state")
    def _compute_is_paid(self):
        for order in self:
            invoices = order.invoice_ids.filtered(lambda inv: inv.state == "posted")
            order.is_paid = bool(invoices) and all(
                invoice.payment_state in ("paid", "in_payment") for invoice in invoices
            )

    @api.depends(
        "ota_payment",
        "invoice_ids.matched_payment_ids.journal_id.type",
    )
    def _compute_calc_payment_type(self):
        for order in self:
            if order.ota_payment:
                order.calc_payment_type = "verrechnungskonto"
                continue
            journal_types = set(order.invoice_ids.matched_payment_ids.journal_id.mapped("type"))
            if journal_types == {"cash"}:
                order.calc_payment_type = "cash"
            elif journal_types == {"bank"}:
                order.calc_payment_type = "banktransfer"
            else:
                order.calc_payment_type = False

    @api.depends("ota_payment")
    def _compute_invoice_status(self):
        res = super()._compute_invoice_status()
        for order in self.filtered(lambda o: o.ota_payment and o.state == "sale"):
            order.invoice_status = "invoiced"
        return res

    @api.depends("rental_start_date", "rental_return_date")
    def _compute_is_ongoing(self):
        now = fields.Datetime.now()
        for order in self:
            order.is_ongoing = bool(
                order.rental_start_date
                and order.rental_return_date
                and order.rental_start_date <= now <= order.rental_return_date
            )

    @api.depends("order_line.product_id.planning_role_id")
    def _compute_planning_role_ids(self):
        for order in self:
            order.planning_role_ids = order.order_line.product_id.planning_role_id

    @api.model_create_multi
    def create(self, vals_list):
        website_channels = {}
        for vals in vals_list:
            if not vals.get("website_id") or vals.get("sale_channel_id"):
                continue
            company_id = vals.get("company_id") or self.env.company.id
            if company_id not in website_channels:
                channel_model = self.env["sale.channel"].sudo()
                channel = channel_model.search(
                    [
                        ("name", "=", "Website"),
                        ("company_id", "=", company_id),
                    ],
                    limit=1,
                )
                if not channel:
                    channel = channel_model.create(
                        {
                            "name": "Website",
                            "company_id": company_id,
                        }
                    )
                website_channels[company_id] = channel
            vals["sale_channel_id"] = website_channels[company_id].id

        orders = super().create(vals_list)
        for order in orders.filtered(
            lambda o: not o.brand_id and (o.website_id or o.sale_channel_id) and o.company_id.default_brand_id
        ):
            order.brand_id = order.company_id.default_brand_id
        return orders

    def _cron_update_is_ongoing(self):
        now = fields.Datetime.now()
        orders = self.search(
            [
                ("rental_start_date", "!=", False),
                ("rental_return_date", "!=", False),
                "|",
                ("is_ongoing", "=", True),
                "&",
                ("rental_start_date", "<=", now),
                ("rental_return_date", ">=", now),
            ]
        )
        orders._compute_is_ongoing()

    @api.depends("order_line.product_id.product_tmpl_id.directions")
    def _compute_direction_info(self):
        for order in self:
            source_products = order.order_line.product_id.product_tmpl_id.filtered("directions")
            directions = source_products.mapped("directions")
            order.directions = "\n\n".join(
                dict.fromkeys(direction.strip() for direction in directions if direction)
            )
            order.direction_product_template_ids = source_products
