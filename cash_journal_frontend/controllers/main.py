import base64
import json
import mimetypes
import re

from odoo import Command, _, fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


class CashJournalFrontend(http.Controller):
    @http.route(
        "/cash/analytic_accounts/search",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def search_analytic_accounts(self, **post):
        user_id = request.env.user
        term = (post.get("term") or "").strip()
        plan_id = self._parse_optional_int(post.get("plan_id"))
        limit = min(self._parse_optional_int(post.get("limit")) or 20, 50)
        selected_company_id = self._get_selected_company(user_id, post.get("company_id"))

        try:
            pattern = re.compile(term or ".*", re.IGNORECASE)
        except re.error as error:
            return request.make_json_response(
                {"error": _("Invalid regular expression: %(error)s") % {"error": str(error)}},
                status=400,
            )

        allowed_company_ids = selected_company_id.ids
        domain = [
            "|",
            ("company_id", "=", False),
            ("company_id", "in", allowed_company_ids),
        ]
        if plan_id:
            domain.append(("plan_id", "=", plan_id))

        has_regex_syntax = bool(re.search(r"[.^$*+?{}\[\]\\|()]", term))
        search_limit = 5000 if has_regex_syntax else limit
        search_domain = list(domain)
        if term and not has_regex_syntax:
            search_domain.extend(
                [
                    "|",
                    ("name", "ilike", term),
                    ("code", "ilike", term),
                ]
            )

        analytic_account_ids = (
            request.env["account.analytic.account"]
            .sudo()
            .search(search_domain, order="plan_id, name", limit=search_limit)
        )
        matches = []
        for analytic_account_id in analytic_account_ids:
            label = analytic_account_id.display_name
            searchable_value = " ".join(
                value
                for value in [
                    analytic_account_id.code or "",
                    analytic_account_id.name or "",
                    analytic_account_id.plan_id.display_name or "",
                    label,
                ]
                if value
            )
            if not pattern.search(searchable_value):
                continue
            matches.append(
                {
                    "id": analytic_account_id.id,
                    "label": label,
                    "plan_id": analytic_account_id.plan_id.id,
                }
            )
            if len(matches) >= limit:
                break

        return request.make_json_response({"results": matches})

    @http.route(
        "/cash/analytic_accounts/create",
        type="http",
        auth="user",
        methods=["POST"],
    )
    def create_analytic_account(self, **post):
        user_id = request.env.user
        name = (post.get("name") or "").strip()
        if not name:
            return request.make_json_response({"error": _("Please enter a name.")}, status=400)

        plan_id = self._get_selected_record(
            "account.analytic.plan",
            post.get("plan_id"),
            request.env["account.analytic.plan"],
        )
        if not plan_id:
            return request.make_json_response({"error": _("Please select an analytic plan first.")}, status=400)

        selected_company_id = self._get_selected_company(user_id, post.get("company_id"))
        analytic_account_id = (
            request.env["account.analytic.account"]
            .sudo()
            .create(
                {
                    "name": name,
                    "plan_id": plan_id.id,
                    "company_id": selected_company_id.id,
                }
            )
        )
        return request.make_json_response(
            {
                "id": analytic_account_id.id,
                "label": analytic_account_id.display_name,
                "plan_id": analytic_account_id.plan_id.id,
            }
        )

    @http.route(
        "/cash/partners/search",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def search_partners(self, **post):
        user_id = request.env.user
        term = (post.get("term") or "").strip()
        limit = min(self._parse_optional_int(post.get("limit")) or 20, 50)
        selected_company_id = self._get_selected_company(user_id, post.get("company_id"))

        try:
            pattern = re.compile(term or ".*", re.IGNORECASE)
        except re.error as error:
            return request.make_json_response(
                {"error": _("Invalid regular expression: %(error)s") % {"error": str(error)}},
                status=400,
            )

        allowed_company_ids = selected_company_id.ids
        domain = [
            "|",
            ("company_id", "=", False),
            ("company_id", "in", allowed_company_ids),
        ]
        has_regex_syntax = bool(re.search(r"[.^$*+?{}\[\]\\|()]", term))
        search_limit = 5000 if has_regex_syntax else limit
        search_domain = list(domain)
        if term and not has_regex_syntax:
            search_domain.extend(
                [
                    "|",
                    "|",
                    "|",
                    ("name", "ilike", term),
                    ("email", "ilike", term),
                    ("ref", "ilike", term),
                    ("vat", "ilike", term),
                ]
            )

        partner_ids = (
            request.env["res.partner"]
            .sudo()
            .search(search_domain, order="complete_name, name", limit=search_limit)
        )
        matches = []
        for partner_id in partner_ids:
            label = partner_id.display_name
            searchable_value = " ".join(
                value
                for value in [
                    partner_id.name or "",
                    partner_id.complete_name or "",
                    partner_id.email or "",
                    partner_id.ref or "",
                    partner_id.vat or "",
                    label,
                ]
                if value
            )
            if not pattern.search(searchable_value):
                continue
            matches.append(
                {
                    "id": partner_id.id,
                    "label": label,
                }
            )
            if len(matches) >= limit:
                break

        return request.make_json_response({"results": matches})

    @http.route(
        "/cash/analytic_distribution/default",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def get_default_analytic_distribution(self, **post):
        user_id = request.env.user
        selected_company_id = self._get_selected_company(user_id, post.get("company_id"))
        allowed_company_ids = selected_company_id.ids

        manual_distribution_id = self._get_selected_manual_distribution(
            user_id,
            post.get("manual_distribution_id"),
            allowed_company_ids,
        )
        analytic_account_id = self._get_selected_record(
            "account.analytic.account",
            post.get("analytic_account_id"),
            user_id.cash_analytic_account_id,
            allowed_company_ids=allowed_company_ids,
        )
        distribution, display = self._get_default_distribution(
            manual_distribution_id,
            analytic_account_id,
        )
        return request.make_json_response({"distribution": distribution, "display": display})

    @http.route(
        "/cash",
        type="http",
        auth="user",
        website=True,
        methods=["GET", "POST"],
        sitemap=False,
    )
    def cash(self, **post):
        user_id = request.env.user
        journal_id = user_id.cash_journal_id
        source_values = post if request.httprequest.method == "POST" else request.params
        values = self._get_cash_page_values(user_id, journal_id, source_values)

        if request.httprequest.method == "POST":
            try:
                if post.get("action") == "analyze":
                    values["form_values"] = self._get_analyzed_form_values(post)
                    values["form_lines"] = self._get_form_lines(post)
                    self._apply_analyzed_values_to_first_line(values["form_values"], values["form_lines"])
                    values["analyzed"] = True
                else:
                    self._create_cash_statement_line(user_id, journal_id, post)
            except (UserError, ValidationError, ValueError) as error:
                values["error"] = str(error)
                values["form_values"] = self._get_form_values(post)
                values["form_lines"] = self._get_form_lines(post)
            else:
                if post.get("action") != "analyze":
                    return request.redirect("/cash?created=1")

        values["created"] = request.params.get("created")
        return request.render("cash_journal_frontend.cash_page", values)

    def _get_cash_page_values(self, user_id, journal_id, source_values=None):
        source_values = source_values or {}
        selected_company_id = self._get_selected_company(user_id, source_values.get("company_id"))
        allowed_company_ids = selected_company_id.ids
        statement_line_model_id = request.env["account.bank.statement.line"]
        recent_line_ids = statement_line_model_id
        if journal_id:
            recent_line_ids = statement_line_model_id.search(
                [
                    ("journal_id", "=", journal_id.id),
                    ("create_uid", "=", user_id.id),
                ],
                limit=10,
            )
        cash_flow_line_ids = self._get_cash_flow_lines(
            journal_id,
            allowed_company_ids,
        )
        selected_analytic_plan_id = (
            self._parse_optional_int(source_values.get("analytic_plan_id")) or user_id.cash_analytic_plan_id.id
        )
        selected_analytic_account_id = self._get_selected_record(
            "account.analytic.account",
            source_values.get("analytic_account_id"),
            user_id.cash_analytic_account_id,
            allowed_company_ids=allowed_company_ids,
        )
        if not selected_analytic_account_id:
            selected_analytic_account_id = self._get_first_analytic_account(
                allowed_company_ids,
                selected_analytic_plan_id,
            )
        selected_manual_distribution_id = self._get_selected_manual_distribution(
            user_id,
            source_values.get("manual_distribution_id"),
            allowed_company_ids,
        )
        default_distribution, default_distribution_display = self._get_default_distribution(
            selected_manual_distribution_id,
            selected_analytic_account_id,
        )
        return {
            "company": selected_company_id,
            "companies": user_id.company_ids,
            "journal": journal_id,
            "today": fields.Date.context_today(user_id),
            "recent_lines": recent_line_ids,
            "cash_flow_lines": cash_flow_line_ids,
            "accounts": request.env["account.account"]
            .sudo()
            .search([("company_ids", "in", allowed_company_ids)], order="code"),
            "analytic_plans": request.env["account.analytic.plan"].sudo().search([]),
            "manual_distributions": request.env["account.analytic.distribution.manual"]
            .sudo()
            .search(
                [
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "in", allowed_company_ids),
                ],
                order="name",
            ),
            "default_company_id": selected_company_id.id,
            "default_account_id": user_id.cash_account_id.id,
            "default_analytic_plan_id": selected_analytic_plan_id,
            "default_analytic_account_id": selected_analytic_account_id.id,
            "default_analytic_account_name": selected_analytic_account_id.display_name,
            "default_analytic_account_display": default_distribution_display,
            "default_analytic_distribution": json.dumps(default_distribution),
            "default_analytic_tag_ids": user_id.cash_analytic_tag_ids,
            "default_manual_distribution_id": selected_manual_distribution_id.id,
            "default_manual_distribution_name": selected_manual_distribution_id.display_name,
            "form_values": {},
            "form_lines": self._get_default_form_lines(
                user_id,
                default_distribution,
                default_distribution_display,
            ),
            "created": False,
            "analyzed": False,
            "error": False,
        }

    def _get_cash_flow_lines(self, journal_id, allowed_company_ids):
        if not journal_id:
            return request.env["account.bank.statement.line"]
        return (
            request.env["account.bank.statement.line"]
            .with_context(allowed_company_ids=allowed_company_ids)
            .search(
                [
                    ("journal_id", "=", journal_id.id),
                    ("company_id", "in", allowed_company_ids),
                ],
                order="date desc, id desc",
            )
        )

    def _get_analyzed_form_values(self, post):
        form_values = self._get_form_values(post)
        image_base64, mimetype = self._get_image_payload(post)

        extracted_values = self._analyze_cash_image(image_base64, mimetype)
        form_values.update(
            {field_name: field_value for field_name, field_value in extracted_values.items() if field_value}
        )
        return form_values

    def _get_form_values(self, post):
        return {
            "date": post.get("date"),
            "payment_ref": post.get("payment_ref"),
            "partner": post.get("partner"),
            "partner_id": post.get("partner_id"),
            "amount": post.get("amount"),
            "company_id": post.get("company_id"),
            "analytic_plan_id": post.get("analytic_plan_id"),
            "manual_distribution_id": post.get("manual_distribution_id"),
            "kassa_only": post.get("kassa_only"),
        }

    def _get_default_form_lines(self, user_id, distribution, distribution_display):
        return [
            {
                "label": "",
                "account_id": user_id.cash_account_id.id,
                "analytic_distribution": json.dumps(distribution),
                "analytic_distribution_display": distribution_display,
                "amount": "",
            }
        ]

    def _get_selected_manual_distribution(self, user_id, posted_manual_distribution_id, allowed_company_ids):
        return self._get_selected_record(
            "account.analytic.distribution.manual",
            posted_manual_distribution_id,
            user_id.cash_manual_distribution_id,
            allowed_company_ids=allowed_company_ids,
        )

    def _get_default_distribution(self, manual_distribution_id, analytic_account_id):
        if manual_distribution_id:
            distribution = self._get_manual_distribution(manual_distribution_id, analytic_account_id)
            if distribution:
                display = manual_distribution_id.display_name
                if analytic_account_id:
                    display = f"{display} / {analytic_account_id.display_name}"
                return distribution, display
        return (
            self._get_default_analytic_distribution(analytic_account_id),
            analytic_account_id.display_name if analytic_account_id else "",
        )

    def _get_manual_distribution(self, manual_distribution_id, override_account_id=None):
        raw_distribution = manual_distribution_id.analytic_distribution or {}
        if not raw_distribution:
            return {}
        account_ids = {
            parsed_id
            for key in raw_distribution
            for part in str(key).split(",")
            if (parsed_id := self._parse_optional_int(part))
        }
        accounts_by_id = {
            account_id.id: account_id
            for account_id in request.env["account.analytic.account"].sudo().browse(list(account_ids)).exists()
        }
        override_plan_id = override_account_id.plan_id.id if override_account_id else False

        distribution = {}
        for key, percentage in raw_distribution.items():
            selected_account_ids = []
            for part in str(key).split(","):
                account_id = accounts_by_id.get(self._parse_optional_int(part))
                if not account_id or (override_account_id and account_id.plan_id.id == override_plan_id):
                    continue
                selected_account_ids.append(account_id)
            if override_account_id:
                selected_account_ids.append(override_account_id)
            if not selected_account_ids:
                continue
            label = " / ".join(account_id.display_name for account_id in selected_account_ids)
            new_key = ",".join(str(account_id.id) for account_id in selected_account_ids)
            distribution[new_key] = {
                "percentage": percentage,
                "label": label,
                "accounts": [
                    {
                        "id": account_id.id,
                        "label": account_id.display_name,
                        "plan_id": account_id.plan_id.id,
                    }
                    for account_id in selected_account_ids
                ],
            }
        return distribution

    def _get_default_analytic_distribution(self, analytic_account_id):
        if not analytic_account_id:
            return {}
        return {
            str(analytic_account_id.id): {
                "percentage": 100.0,
                "label": analytic_account_id.display_name,
                "accounts": [
                    {
                        "id": analytic_account_id.id,
                        "label": analytic_account_id.display_name,
                        "plan_id": analytic_account_id.plan_id.id,
                    }
                ],
            }
        }

    def _get_form_lines(self, post):
        labels = self._get_post_list(post, "line_label")
        account_ids = self._get_post_list(post, "line_account_id")
        analytic_distributions = self._get_post_list(post, "line_analytic_distribution")
        analytic_distribution_displays = self._get_post_list(post, "line_analytic_distribution_display")
        amounts = self._get_post_list(post, "line_amount")
        line_count = max(
            len(labels),
            len(account_ids),
            len(analytic_distributions),
            len(analytic_distribution_displays),
            len(amounts),
            1,
        )

        lines = []
        for line_index in range(line_count):
            line_values = {
                "label": self._get_list_value(labels, line_index),
                "account_id": self._get_list_value(account_ids, line_index),
                "analytic_distribution": self._get_list_value(analytic_distributions, line_index),
                "analytic_distribution_display": self._get_list_value(analytic_distribution_displays, line_index),
                "amount": self._get_list_value(amounts, line_index),
            }
            if any(line_values.values()):
                lines.append(line_values)
        return lines or [{"label": "", "account_id": "", "analytic_distribution": "{}", "amount": ""}]

    def _apply_analyzed_values_to_first_line(self, form_values, form_lines):
        if not form_lines:
            return
        first_line = form_lines[0]
        if not first_line.get("label"):
            first_line["label"] = form_values.get("payment_ref") or form_values.get("partner")
        if not first_line.get("amount"):
            first_line["amount"] = form_values.get("amount")

    def _get_post_list(self, post, field_name):
        if request.httprequest.method == "POST":
            return request.httprequest.form.getlist(field_name)
        value = post.get(field_name)
        if isinstance(value, list):
            return value
        return [value] if value else []

    def _get_list_value(self, values, index):
        if index >= len(values):
            return ""
        return values[index]

    def _get_image_payload(self, post, required=True):
        image = post.get("receipt_image")
        if image and getattr(image, "filename", ""):
            return (
                base64.b64encode(image.read()).decode("ascii"),
                image.mimetype or "image/jpeg",
            )

        captured_image = (post.get("captured_receipt_image") or "").strip()
        data_url_match = re.match(
            r"^data:(?P<mimetype>image/[a-zA-Z0-9.+-]+);base64,(?P<data>.+)$",
            captured_image,
        )
        if data_url_match:
            return data_url_match.group("data"), data_url_match.group("mimetype")

        if required:
            raise UserError(_("Please capture or upload an image first."))
        return None, None

    def _attach_receipt_image(self, statement_line_id, image_base64, mimetype):
        extension = mimetypes.guess_extension(mimetype) or ".jpg"
        statement_line_id.message_post(attachments=[(f"receipt{extension}", base64.b64decode(image_base64))])

    def _analyze_cash_image(self, image_base64, mimetype):
        try:
            import openai
        except ImportError as error:
            raise UserError(_("The Python OpenAI library is not installed on this Odoo server.")) from error

        if "ai.config" not in request.env:
            raise UserError(_("The Odoo AI configuration module is not installed."))

        config_id = (
            request.env["ai.config"]
            .sudo()
            .search(
                [
                    ("active", "=", True),
                    ("type", "=", "chatgpt"),
                    ("api_key", "!=", False),
                ],
                limit=1,
            )
        )
        if not config_id:
            raise UserError(_("No active ChatGPT AI configuration with an API key was found."))

        client = openai.OpenAI(api_key=config_id.api_key)
        try:
            response = client.chat.completions.create(
                model=config_id.model or "gpt-5-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Analyze this receipt or cash transaction image. "
                                    "Return only a JSON object with these keys: "
                                    "date, payment_ref, partner, direction, amount. "
                                    "Use ISO date YYYY-MM-DD or null. "
                                    "Use direction 'out' for expenses/payments and 'in' "
                                    "for received cash. Use a positive decimal amount "
                                    "without currency symbols."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mimetype};base64,{image_base64}",
                                },
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"},
            )
        except openai.OpenAIError as error:
            raise UserError(_("OpenAI could not analyze the image: %(error)s") % {"error": str(error)}) from error
        content = response.choices[0].message.content or "{}"
        try:
            extracted_values = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if not json_match:
                raise UserError(_("The AI response did not contain usable transaction data.")) from None
            try:
                extracted_values = json.loads(json_match.group(0))
            except json.JSONDecodeError as error:
                raise UserError(_("The AI response did not contain usable transaction data.")) from error

        return self._normalize_analyzed_values(extracted_values)

    def _normalize_analyzed_values(self, extracted_values):
        date_value = extracted_values.get("date")
        if date_value:
            try:
                date_value = fields.Date.to_string(fields.Date.to_date(date_value))
            except (TypeError, ValueError):
                date_value = False

        direction = extracted_values.get("direction")
        if direction not in ("in", "out"):
            direction = "out"

        amount = extracted_values.get("amount")
        try:
            signed_amount = abs(self._parse_amount(amount))
            if direction == "out":
                signed_amount = -signed_amount
            amount = f"{signed_amount:.2f}"
        except ValueError:
            amount = False

        payment_ref = (extracted_values.get("payment_ref") or "").strip()
        partner = (extracted_values.get("partner") or "").strip()
        if not payment_ref:
            payment_ref = partner

        return {
            "date": date_value,
            "payment_ref": payment_ref,
            "partner": partner,
            "amount": amount,
        }

    def _create_cash_statement_line(self, user_id, journal_id, post):
        if not journal_id:
            raise UserError(_("No cash journal is configured on your user."))
        if journal_id.type != "cash":
            raise UserError(_("Your configured journal must be a cash journal."))

        selected_company_id = self._get_selected_company(user_id, post.get("company_id"))
        allowed_company_ids = selected_company_id.ids
        kassa_only = bool(post.get("kassa_only"))

        partner_id = self._get_selected_record(
            "res.partner",
            post.get("partner_id"),
            request.env["res.partner"],
            allowed_company_ids=allowed_company_ids,
        )
        if not partner_id and (partner_term := (post.get("partner") or "").strip()):
            partner_id = request.env["res.partner"].search(
                [
                    ("company_id", "in", [False, *allowed_company_ids]),
                    "|",
                    ("name", "ilike", partner_term),
                    ("email", "ilike", partner_term),
                ],
                limit=1,
            )

        statement_line_values = {
            "journal_id": journal_id.id,
            "date": post.get("date") or fields.Date.context_today(request.env.user),
        }
        if kassa_only:
            payment_ref = (post.get("payment_ref") or "").strip()
            if not payment_ref:
                raise UserError(_("Please enter a label."))
            signed_amount = self._parse_amount(post.get("amount"))
            if not signed_amount:
                raise UserError(_("Please enter a non-zero amount."))
            statement_line_values["payment_ref"] = payment_ref
            statement_line_values["amount"] = signed_amount
        else:
            payment_ref = self._get_lines_payment_ref(post)
            if not payment_ref:
                raise UserError(_("Please enter a label on at least one line."))

            selected_manual_distribution_id = self._get_selected_manual_distribution(
                user_id,
                post.get("manual_distribution_id"),
                allowed_company_ids,
            )
            cash_line_values = self._prepare_cash_line_values(
                user_id,
                post,
                allowed_company_ids,
                payment_ref,
                selected_manual_distribution_id,
            )
            total_amount = sum(line_values["signed_amount"] for line_values in cash_line_values)
            if not total_amount:
                raise UserError(_("Please enter at least one non-zero line amount."))

            statement_line_values["payment_ref"] = payment_ref
            statement_line_values["amount"] = total_amount
            statement_line_values["line_ids"] = self._prepare_move_line_commands(
                journal_id, partner_id, total_amount, cash_line_values
            )

        if partner_id:
            statement_line_values["partner_id"] = partner_id.id

        statement_line_id = (
            request.env["account.bank.statement.line"]
            .with_context(allowed_company_ids=allowed_company_ids)
            .create(statement_line_values)
        )

        image_base64, mimetype = self._get_image_payload(post, required=False)
        if image_base64:
            self._attach_receipt_image(statement_line_id, image_base64, mimetype)

        return statement_line_id

    def _get_lines_payment_ref(self, post):
        labels = [
            label
            for line_values in self._get_form_lines(post)
            if (label := (line_values.get("label") or "").strip())
        ]
        return ", ".join(labels)

    def _prepare_cash_line_values(self, user_id, post, allowed_company_ids, payment_ref, manual_distribution_id):
        cash_line_values = []
        for line_values in self._get_form_lines(post):
            signed_amount = self._parse_amount(line_values.get("amount"))
            if not signed_amount:
                continue

            account_id = self._get_selected_record(
                "account.account",
                line_values.get("account_id"),
                user_id.cash_account_id,
                allowed_company_ids=allowed_company_ids,
            )
            if not account_id:
                raise UserError(_("Please select an account on every cash line."))

            analytic_distribution = self._get_valid_analytic_distribution(
                line_values.get("analytic_distribution"),
                allowed_company_ids,
            )

            cash_line_values.append(
                {
                    "name": (line_values.get("label") or "").strip() or payment_ref,
                    "account_id": account_id,
                    "analytic_distribution": analytic_distribution,
                    "analytic_tag_ids": user_id.cash_analytic_tag_ids.ids,
                    "manual_distribution_id": manual_distribution_id.id,
                    "signed_amount": signed_amount,
                }
            )

        if not cash_line_values:
            raise UserError(_("Please enter at least one non-zero line amount."))
        return cash_line_values

    def _get_valid_analytic_distribution(self, distribution_json, allowed_company_ids):
        try:
            distribution = json.loads(distribution_json or "{}")
        except json.JSONDecodeError as error:
            raise UserError(_("Please save the analytic distribution again.")) from error
        if not isinstance(distribution, dict):
            raise UserError(_("Please save the analytic distribution again."))

        analytic_account_model_id = request.env["account.analytic.account"].sudo()
        valid_distribution = {}
        total_percentage = 0.0
        for analytic_account_key, percentage in distribution.items():
            analytic_account_ids = [
                analytic_account_id
                for key_part in str(analytic_account_key).split(",")
                if (analytic_account_id := self._parse_optional_int(key_part))
            ]
            if not analytic_account_ids:
                continue
            if isinstance(percentage, dict):
                percentage = percentage.get("percentage")
            try:
                percentage = float(percentage)
            except (TypeError, ValueError):
                continue
            if percentage <= 0:
                continue
            account_ids = analytic_account_model_id.browse(analytic_account_ids).exists()
            if len(account_ids) != len(set(analytic_account_ids)):
                continue
            if any(
                account_id.company_id and account_id.company_id.id not in allowed_company_ids
                for account_id in account_ids
            ):
                continue
            distribution_key = ",".join(str(account_id.id) for account_id in account_ids.sorted("plan_id"))
            valid_distribution[distribution_key] = percentage
            total_percentage += percentage

        if not valid_distribution:
            raise UserError(_("Please define an analytic distribution on every cash line."))
        if abs(total_percentage - 100.0) > 0.0001:
            raise UserError(_("The analytic distribution must total 100%."))
        return valid_distribution

    def _prepare_move_line_commands(self, journal_id, partner_id, total_amount, cash_line_values):
        currency_id = journal_id.currency_id or journal_id.company_id.currency_id
        liquidity_amount = total_amount
        move_line_commands = [
            Command.create(
                {
                    "name": cash_line_values[0]["name"],
                    "partner_id": partner_id.id,
                    "account_id": journal_id.default_account_id.id,
                    "currency_id": currency_id.id,
                    "amount_currency": liquidity_amount,
                    "debit": liquidity_amount if liquidity_amount > 0 else 0.0,
                    "credit": -liquidity_amount if liquidity_amount < 0 else 0.0,
                }
            )
        ]
        for cash_line_value in cash_line_values:
            counterpart_amount = -cash_line_value["signed_amount"]
            counterpart_line = {
                "name": cash_line_value["name"],
                "partner_id": partner_id.id,
                "account_id": cash_line_value["account_id"].id,
                "currency_id": currency_id.id,
                "amount_currency": counterpart_amount,
                "debit": counterpart_amount if counterpart_amount > 0 else 0.0,
                "credit": -counterpart_amount if counterpart_amount < 0 else 0.0,
            }
            if cash_line_value["analytic_distribution"]:
                counterpart_line["analytic_distribution"] = cash_line_value["analytic_distribution"]
            if cash_line_value["analytic_tag_ids"]:
                counterpart_line["analytic_tag_ids"] = [Command.set(cash_line_value["analytic_tag_ids"])]
            if cash_line_value["manual_distribution_id"]:
                counterpart_line["manual_distribution_id"] = cash_line_value["manual_distribution_id"]
            move_line_commands.append(Command.create(counterpart_line))
        return move_line_commands

    def _get_allowed_company_ids(self, user_id):
        if user_id.cash_company_id:
            return user_id.cash_company_id.ids
        return user_id.company_ids.ids or user_id.company_id.ids

    def _get_selected_company(self, user_id, posted_company_id=False):
        allowed_company_ids = user_id.company_ids or user_id.company_id
        default_company_id = user_id.cash_company_id or user_id.company_id
        selected_company_id = self._get_selected_record(
            "res.company",
            posted_company_id,
            default_company_id,
        )
        if selected_company_id in allowed_company_ids:
            return selected_company_id
        return allowed_company_ids[:1]

    def _get_first_analytic_account(self, allowed_company_ids, plan_id=False):
        domain = [
            "|",
            ("company_id", "=", False),
            ("company_id", "in", allowed_company_ids),
        ]
        if plan_id:
            domain.append(("plan_id", "=", plan_id))
        return request.env["account.analytic.account"].sudo().search(domain, order="plan_id, name", limit=1)

    def _get_selected_record(self, model_name, posted_id, default_record_id, allowed_company_ids=None):
        if not posted_id:
            return default_record_id
        parsed_id = self._parse_optional_int(posted_id)
        if not parsed_id:
            return default_record_id
        record_id = request.env[model_name].sudo().browse(parsed_id).exists()
        if not record_id:
            return default_record_id
        if allowed_company_ids is not None and "company_id" in record_id._fields:
            company_id = record_id.company_id
            if company_id and company_id.id not in allowed_company_ids:
                return default_record_id
        if allowed_company_ids is not None and "company_ids" in record_id._fields:
            record_company_ids = record_id.company_ids.ids
            if record_company_ids and not set(record_company_ids).intersection(allowed_company_ids):
                return default_record_id
        return request.env[model_name].browse(record_id.id)

    def _parse_optional_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return False

    def _parse_amount(self, amount):
        normalized_amount = re.sub(r"[^0-9,.-]", "", str(amount or ""))
        if "," in normalized_amount and "." in normalized_amount:
            if normalized_amount.rfind(",") > normalized_amount.rfind("."):
                normalized_amount = normalized_amount.replace(".", "").replace(",", ".")
            else:
                normalized_amount = normalized_amount.replace(",", "")
        else:
            normalized_amount = normalized_amount.replace(",", ".")
        return float(normalized_amount)
