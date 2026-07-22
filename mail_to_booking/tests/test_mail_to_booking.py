import json
from io import BytesIO
from unittest.mock import Mock, patch

from reportlab.pdfgen import canvas

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

DEEPSEEK_POST_PATH = "odoo.addons.mail_to_booking.models.mail_to_booking.requests.post"
SALE_ORDER_ACTION_CONFIRM_PATH = "odoo.addons.sale.models.sale_order.SaleOrder.action_confirm"

# Real sample: lisigruen.at, mail.to.booking id 1, an Alpacacamping booking
# mail forwarded through buchungen@weingartmair.eu.
ALPACACAMPING_MSG_DICT = {
    "subject": "Dein Angebot wurde gebucht",
    "email_from": '"Alpacacamping" <kontakt@alpacacamping.de>',
    "body": (
        "Dein Angebot Camping für Gartenliebhaber am Bauernhof wurde für "
        "2 Nächte gebucht.\n"
        "Buchungscode: b0YRT2\n"
        "Gebucht: Camping für Gartenliebhaber am Bauernhof\n"
        "Checkin: 17.Jul.2026\n"
        "Checkout: 19.Jul.2026\n"
        "Anzahl der Nächte: 2 Nächte\n"
        "Anzahl der Fahrzeuge: 1\n"
        "Name des Gastes: Jürgen Gasteiger\n"
        "Nachricht deines Gastes: Hallo, wir, Monika und Jürgen Gasteiger "
        "wollen uns eine kleine Auszeit gönnen und freuen uns sehr, wenn "
        "wir bei euch mit übernachten können. Wir kommen mit unserem "
        "Wohnwagen."
    ),
}

ALPACACAMPING_EXTRACTION = {
    "is_booking": True,
    "platform": "Alpacacamping",
    "code": "b0YRT2",
    "guest_name": "Jürgen Gasteiger",
    "phone": "",
    "email": "",
    "checkin_date": "2026-07-17",
    "checkout_date": "2026-07-19",
    "nights": 2,
    "adults": 0,
    "vehicles": 1,
    "price_unit": 0,
    "product_hint": "Camping für Gartenliebhaber am Bauernhof",
    "message": (
        "Hallo, wir, Monika und Jürgen Gasteiger wollen uns eine kleine "
        "Auszeit gönnen und freuen uns sehr, wenn wir bei euch mit "
        "übernachten können. Wir kommen mit unserem Wohnwagen."
    ),
}

# Real sample: lisigruen.at, mail.to.booking id 5, a website reservation-form
# submission ("Diese Nachricht wurde auf Ihrer Website veröffentlicht!")
# forwarded by mail. DeepSeek originally classified this as is_booking=False
# because it reads like an automated notification rather than free-form
# prose - even though it carries a guest name, contact details and a
# concrete date range. The system prompt was updated to treat this pattern
# as a direct booking inquiry; this fixture pins the corrected behavior.
WEBSITE_FORM_MSG_DICT = {
    "subject": "Fwd: Reservierung",
    "email_from": '"Nikolaus Weingartmair" <weinni2000@gmail.com>',
    "body": (
        "---------- Forwarded message ---------\n"
        "From: Nikolaus Weingartmair e.U-Formulareinreichung "
        "<weinni2000@gmail.com>\n"
        "Subject: Reservierung\n"
        "To: <weinni2000@gmail.com>\n\n"
        "Diese Nachricht wurde auf Ihrer Website veröffentlicht!\n"
        "___________\n"
        "Dein Name : Philipp Laven\n"
        "Telefonnummer : +4915112356486\n"
        "E-Mail : nikolaus@weingartmair.eu\n"
        "Your Mail : phil.laven@freenet.de\n"
        "Personen (ab 18. J) : 2\n"
        "Fahrzeug : Van\n"
        "von : 07.08.2026 12:00:00\n"
        "bis : 08.08.2026 12:00:00\n"
        "Anmerkungen : Gerne im grünen. Danke"
    ),
}

WEBSITE_FORM_EXTRACTION = {
    "is_booking": True,
    "platform": "",
    "code": "",
    "guest_name": "Philipp Laven",
    "phone": "+4915112356486",
    "email": "phil.laven@freenet.de",
    "checkin_date": "2026-08-07",
    "checkout_date": "2026-08-08",
    "nights": 1,
    "adults": 2,
    "vehicles": 1,
    "price_unit": None,
    "product_hint": "Van",
    "message": "Gerne im grünen. Danke",
}


def _deepseek_response(extraction):
    return Mock(
        raise_for_status=lambda: None,
        json=lambda: {"choices": [{"message": {"content": json.dumps(extraction)}}]},
    )


def _make_pdf(text):
    buffer = BytesIO()
    pdf_canvas = canvas.Canvas(buffer)
    pdf_canvas.drawString(100, 750, text)
    pdf_canvas.save()
    return buffer.getvalue()


class TestMailToBooking(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.deepseek_api_key = "test-key"
        cls.server_id = cls.env["fetchmail.server"].create(
            {
                "name": "Test Alpacacamping Inbox",
                "server_type": "imap",
                "server": "mail.example.com",
                "user": "buchungen@example.com",
                "password": "secret",
                "mail_to_booking_enabled": True,
            }
        )

    def _message_new(self, msg_dict, extraction=None):
        with patch(
            DEEPSEEK_POST_PATH,
            return_value=_deepseek_response(extraction or ALPACACAMPING_EXTRACTION),
        ):
            return (
                self.env["mail.to.booking"]
                .with_context(default_fetchmail_server_id=self.server_id.id)
                .message_new(dict(msg_dict))
            )

    def test_alpacacamping_mail_without_matching_product(self):
        """The product_hint DeepSeek extracts is the platform's own
        marketing copy for the listing ("Camping für Gartenliebhaber am
        Bauernhof"), which never textually overlaps with an internal
        product name. No mail.to.booking.product.mapping row exists yet
        either, so no product can be resolved - no sale.order is created
        and the record is left in the 'no_product' state for an admin to
        map it via the product mapping wizard."""
        record = self._message_new(ALPACACAMPING_MSG_DICT)

        self.assertEqual(record.state, "no_product")
        self.assertEqual(record.sale_channel_id.name, "Alpacacamping")
        self.assertEqual(record.sale_channel_id.email, "kontakt@alpacacamping.de")
        self.assertEqual(record.booking_code, "b0YRT2")
        self.assertEqual(record.guest_name, "Jürgen Gasteiger")
        self.assertEqual(str(record.checkin_date), "2026-07-17")
        self.assertEqual(str(record.checkout_date), "2026-07-19")
        self.assertEqual(record.nights, 2)
        self.assertEqual(record.vehicles, 1)
        self.assertFalse(record.sale_order_id)
        self.assertFalse(record.product_id)

    def test_mapping_wizard_resolves_product_and_creates_booking(self):
        """Once an admin maps the platform's product_hint to a real
        product for this sale channel (the flow driven by the "Choose
        Product" wizard), processing again resolves product_id through the
        mapping table and finally creates the sale.order - without calling
        DeepSeek again, since all the booking data was already extracted."""
        record = self._message_new(ALPACACAMPING_MSG_DICT)
        self.assertEqual(record.state, "no_product")

        product_id = self.env["product.product"].create(
            {"name": "Stellplatz Bauernhof (2P)", "rent_ok": True, "sale_ok": True}
        )
        wizard_id = (
            self.env["mail.to.booking.product.mapping.wizard"]
            .with_context(active_id=record.id)
            .create({"product_id": product_id.id})
        )
        self.assertEqual(wizard_id.sale_channel_id, record.sale_channel_id)
        self.assertEqual(wizard_id.product_hint, record.product_hint)

        wizard_id.action_confirm()

        self.assertEqual(record.state, "created")
        self.assertEqual(record.product_id, product_id)
        self.assertTrue(record.sale_order_id)

    def test_website_form_reservation_is_recognized_as_a_booking(self):
        """A forwarded website reservation-form submission ("Diese
        Nachricht wurde auf Ihrer Website veröffentlicht!") must be
        recognized as a direct booking inquiry - it carries a guest name,
        contact details and a concrete date range, even though it is
        phrased as an automated notification rather than free-form prose."""
        record = self._message_new(WEBSITE_FORM_MSG_DICT, extraction=WEBSITE_FORM_EXTRACTION)

        self.assertTrue(record.is_booking)
        self.assertNotEqual(record.state, "skipped")
        self.assertEqual(record.sale_channel_id.name, "Direct")
        self.assertEqual(record.guest_name, "Philipp Laven")
        self.assertEqual(record.phone, "+4915112356486")
        self.assertEqual(record.email, "phil.laven@freenet.de")
        self.assertEqual(str(record.checkin_date), "2026-08-07")
        self.assertEqual(str(record.checkout_date), "2026-08-08")
        self.assertEqual(record.adults, 2)
        self.assertEqual(record.product_hint, "Van")

    def test_allowed_products_matched_without_mapping_when_confident(self):
        """When the server restricts matching to a fixed allowed_product_ids
        list, a product can be resolved straight away - without a
        pre-existing mail.to.booking.product.mapping row - as long as
        DeepSeek is reasonably confident about which candidate matches. The
        successful match is then cached as a mapping for next time."""
        van_product_id = self.env["product.product"].create(
            {"name": "Stellplatz Van (2P)", "rent_ok": True, "sale_ok": True}
        )
        tent_product_id = self.env["product.product"].create(
            {"name": "Zeltplatz (2P)", "rent_ok": True, "sale_ok": True}
        )
        self.server_id.allowed_product_ids = [(6, 0, [van_product_id.id, tent_product_id.id])]

        responses = [
            _deepseek_response(WEBSITE_FORM_EXTRACTION),
            _deepseek_response({"match_index": 1}),
        ]
        with patch(DEEPSEEK_POST_PATH, side_effect=responses):
            record = (
                self.env["mail.to.booking"]
                .with_context(default_fetchmail_server_id=self.server_id.id)
                .message_new(dict(WEBSITE_FORM_MSG_DICT))
            )

        self.assertEqual(record.product_id, van_product_id)
        self.assertEqual(record.state, "created")
        mapping_id = self.env["mail.to.booking.product.mapping"].search(
            [
                ("sale_channel_id", "=", record.sale_channel_id.id),
                ("product_hint", "=", "Van"),
            ]
        )
        self.assertEqual(mapping_id.product_id, van_product_id)

    def test_allowed_products_not_matched_when_uncertain(self):
        """If DeepSeek isn't reasonably confident about any of the allowed
        products, no product is guessed - the record is left in
        'no_product' instead of picking an arbitrary candidate."""
        van_product_id = self.env["product.product"].create(
            {"name": "Stellplatz Van (2P)", "rent_ok": True, "sale_ok": True}
        )
        self.server_id.allowed_product_ids = [(6, 0, [van_product_id.id])]

        responses = [
            _deepseek_response(WEBSITE_FORM_EXTRACTION),
            _deepseek_response({"match_index": None}),
        ]
        with patch(DEEPSEEK_POST_PATH, side_effect=responses):
            record = (
                self.env["mail.to.booking"]
                .with_context(default_fetchmail_server_id=self.server_id.id)
                .message_new(dict(WEBSITE_FORM_MSG_DICT))
            )

        self.assertEqual(record.state, "no_product")
        self.assertFalse(record.product_id)

    def test_confirm_warning_when_sale_order_confirmation_fails(self):
        """The booking must still be created even if the automatic order
        confirmation fails afterwards - the failure surfaces as a warning
        on the mail record instead of being silently swallowed or blocking
        booking creation entirely."""
        product_id = self.env["product.product"].create(
            {"name": "Stellplatz Bauernhof (2P)", "rent_ok": True, "sale_ok": True}
        )
        channel_id = (
            self.env["sale.channel"].sudo().create({"name": "Alpacacamping", "company_id": self.env.company.id})
        )
        self.env["mail.to.booking.product.mapping"].create(
            {
                "sale_channel_id": channel_id.id,
                "product_hint": "Camping für Gartenliebhaber am Bauernhof",
                "product_id": product_id.id,
            }
        )

        with patch(
            SALE_ORDER_ACTION_CONFIRM_PATH,
            side_effect=UserError("No fiscal year configured."),
        ):
            record = self._message_new(ALPACACAMPING_MSG_DICT)

        self.assertEqual(record.state, "created")
        self.assertTrue(record.sale_order_id)
        self.assertIn("No fiscal year configured.", record.confirm_warning)

    def test_direct_inquiry_from_private_person_creates_direct_channel(self):
        """A direct guest inquiry (no booking platform involved) comes back
        from DeepSeek with an empty "platform", per the system prompt. That
        must resolve to a "Direct" sale channel, created on first use,
        rather than a vague placeholder like "Unknown Platform"."""
        extraction = dict(ALPACACAMPING_EXTRACTION, platform="")
        msg_dict = dict(
            ALPACACAMPING_MSG_DICT,
            email_from='"Jürgen Gasteiger" <juergen.gasteiger@example.com>',
        )
        self.assertFalse(self.env["sale.channel"].search([("name", "=ilike", "Direct")], limit=1))

        record = self._message_new(msg_dict, extraction=extraction)

        self.assertEqual(record.sale_channel_id.name, "Direct")

    def test_extract_pdf_attachments_text(self):
        pdf_bytes = _make_pdf("Booking code: XYZ123")
        text = self.env["mail.to.booking"]._extract_pdf_attachments_text(
            [("voucher.pdf", pdf_bytes), ("ignored.txt", b"not a pdf")]
        )
        self.assertIn("Booking code: XYZ123", text)

    def test_message_new_appends_pdf_attachment_text_to_mail_body(self):
        """A booking confirmation that only names the offer in an attached
        PDF (common for voucher-style platform emails) must still surface
        that text in mail_body, so DeepSeek sees it too."""
        msg_dict = dict(ALPACACAMPING_MSG_DICT)
        msg_dict["attachments"] = [
            ("voucher.pdf", _make_pdf("Voucher reference: PDF-ONLY-CODE")),
        ]
        record = self._message_new(msg_dict)
        self.assertIn("Voucher reference: PDF-ONLY-CODE", record.mail_body)
