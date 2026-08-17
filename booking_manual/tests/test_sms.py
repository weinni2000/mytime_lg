from odoo.tests.common import TransactionCase

from ..sms import extract_booking_code


class TestBookingSms(TransactionCase):
    def test_extracts_booking_code(self):
        test_messages = (
            ("Dein Booking.com Sicherheitscode lautet: 123456", "123456"),
            ("Booking.com verification code: 987 654", "987654"),
            ("Dein Bestätigungscode ist 4567. Nicht weitergeben.", "4567"),
            ("OTP: 12-34-56", "123456"),
            ("Code 87654321", "87654321"),
        )
        for message, expected_code in test_messages:
            with self.subTest(message=message):
                self.assertEqual(extract_booking_code(message), expected_code)

    def test_rejects_message_without_code(self):
        self.assertFalse(extract_booking_code("Booking.com Anmeldung angefordert"))
        self.assertFalse(extract_booking_code(""))
        self.assertFalse(extract_booking_code(None))
