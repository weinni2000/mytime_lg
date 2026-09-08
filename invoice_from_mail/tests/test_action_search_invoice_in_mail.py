from odoo.tests import tagged
from odoo.tests.common import TransactionCase

STATEMENT_LINE_ID = 12245


@tagged("post_install", "-at_install")
class TestActionSearchInvoiceInMail(TransactionCase):
    """Integration test hitting the real `gog` CLI / Gmail account.

    Verifies statement line 12245 on lisigruen.at (the "AR 5035/2026" Ackerl
    Handels GmbH bank transaction) resolves to the matching invoice email and
    its PDF attachment.
    """

    def test_finds_ackerl_invoice_5035(self):
        line = self.env["account.bank.statement.line"].browse(STATEMENT_LINE_ID)
        if not line.exists():
            self.skipTest(f"Statement line {STATEMENT_LINE_ID} does not exist on this database.")

        match = line._find_invoice_mail()
        self.assertTrue(match, "No matching invoice email with a PDF was found.")

        message = line._gog_get_message(match["message_id"])
        sender = message.get("headers", {}).get("from", "")
        self.assertIn("ackerl", sender.lower(), f"Matched mail is not from Ackerl: {sender!r}")
        self.assertIn(
            "5035",
            match["attachment"]["filename"],
            f"Attached PDF does not reference invoice 5035: {match['attachment']['filename']!r}",
        )

        action = line.action_search_invoice_in_mail()
        self.assertTrue(action, "action_search_invoice_in_mail() returned no action.")
