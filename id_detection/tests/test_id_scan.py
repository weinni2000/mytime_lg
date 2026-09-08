import base64
from io import BytesIO
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..models.res_partner import _crop_to_document, _detect_document_box, _detect_text_rotation

_TEST_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _document_like_text_image():
    """A synthetic photo with enough printed text for Tesseract OSD to work with."""
    image = Image.new("RGB", (900, 600), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(_TEST_FONT_PATH, 32)
    lines = [
        "BUNDESREPUBLIK DEUTSCHLAND",
        "PERSONALAUSWEIS",
        "ERIKA MUSTERMANN",
        "GEBURTSDATUM 01.01.1990",
        "MUSTERSTADT DEUTSCH",
        "GUELTIG BIS 01.01.2035",
        "DOKUMENTENNUMMER XX0000000",
    ]
    for i, line in enumerate(lines):
        draw.text((40, 40 + i * 70), line, fill=(0, 0, 0), font=font)
    return image


def _image_b64(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


def _photo_with_document(
    background=(20, 20, 20), document=(230, 230, 230), size=(400, 300), box=(60, 50, 340, 250)
):
    """A synthetic photo: a light rectangle (the "document") on a dark background."""
    image = Image.new("RGB", size, background)
    ImageDraw.Draw(image).rectangle(box, fill=document)
    return image


@tagged("post_install", "-at_install")
class TestDocumentCrop(TransactionCase):
    """Local (non-AI) document-boundary detection used to pre-crop scans."""

    def test_detects_document_rectangle(self):
        box = (60, 50, 340, 250)
        detected = _detect_document_box(_photo_with_document(box=box))
        self.assertIsNotNone(detected)
        for detected_edge, expected_edge in zip(detected, box, strict=True):
            self.assertAlmostEqual(detected_edge, expected_edge, delta=10)

    def test_crop_to_document_shrinks_the_photo(self):
        image = _photo_with_document()
        cropped = _crop_to_document(image)
        self.assertLess(cropped.width * cropped.height, image.width * image.height)

    def test_falls_back_to_original_without_a_confident_rectangle(self):
        # A flat, featureless photo has no rectangle to detect.
        image = Image.new("RGB", (400, 300), (128, 128, 128))
        self.assertIsNone(_detect_document_box(image))
        self.assertEqual(_crop_to_document(image).size, image.size)

    def test_ignores_a_larger_non_card_shaped_region(self):
        """Regression test: a big square-ish background region (e.g. a floor
        tile or door panel in a hand-held photo) must not be picked over a
        smaller, correctly ID-card-proportioned region, even though it has a
        larger area. An early version had no aspect-ratio check and would
        happily crop to whatever large quadrilateral it found first.
        """
        image = Image.new("RGB", (500, 350), (20, 20, 20))
        draw = ImageDraw.Draw(image)
        # Near-square "clutter" region (~1:1) -- larger area than the card below,
        # but still above the minimum-area threshold on its own.
        draw.rectangle((10, 10, 230, 230), fill=(200, 200, 200))
        # ID-card-proportioned (~1.56:1) region, smaller but plausibly card-sized.
        card_box = (240, 80, 490, 240)
        draw.rectangle(card_box, fill=(235, 235, 235))

        detected = _detect_document_box(image)
        self.assertIsNotNone(detected)
        left, top, right, bottom = detected
        width, height = right - left, bottom - top
        self.assertAlmostEqual(
            width / height, (card_box[2] - card_box[0]) / (card_box[3] - card_box[1]), delta=0.3
        )
        # Detected box should overlap the card region, not the clutter square.
        self.assertGreater(left, 230)


@tagged("post_install", "-at_install")
class TestTextRotation(TransactionCase):
    """Local (non-AI) text-orientation detection via Tesseract OSD.

    Regression coverage for a real scan where the model's own clockwise_rotation
    guess put the processed document upside down: this local signal is now
    preferred over the model's guess whenever it can find enough text to be
    confident, since it reads the printed text directly instead of guessing.
    """

    def test_detects_rotation_needed_to_make_text_upright(self):
        image = _document_like_text_image()
        for applied_rotation in (0, 90, 180, 270):
            rotated = image.rotate(-applied_rotation, expand=True)
            detected = _detect_text_rotation(rotated)
            with self.subTest(applied_rotation=applied_rotation):
                # Rotating the already-rotated image by the detected amount
                # must bring it back to (a multiple of 360 from) upright.
                self.assertIsNotNone(detected)
                self.assertEqual((applied_rotation + detected) % 360, 0)

    def test_returns_none_without_enough_text(self):
        image = Image.new("RGB", (400, 300), (255, 255, 255))
        self.assertIsNone(_detect_text_rotation(image))


@tagged("post_install", "-at_install")
class TestFaceDetection(TransactionCase):
    """Smoke test for the YuNet face detector integration.

    A real face photo can't be used here (it would mean committing a real,
    identifiable person's photo to the repository), so this only exercises
    that the bundled ONNX model loads and the detector runs end to end --
    it does not verify detection accuracy on an actual face.
    """

    def test_no_face_found_on_a_blank_photo(self):
        image = Image.new("RGB", (400, 300), (200, 200, 200))
        self.assertFalse(self.env["res.partner"]._detect_upright_face(image))


@tagged("post_install", "-at_install")
class TestIdScan(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "New Guest",
                "company_type": "person",
                "x_id_document_front": _image_b64(_photo_with_document()),
                "x_id_document_back": _image_b64(_photo_with_document(document=(210, 210, 240))),
            }
        )

    @staticmethod
    def _extraction(**overrides):
        extraction = {
            "first_name": "Anna",
            "last_name": "Vzorová",
            "birth_date": "1989-03-23",
            "document_type": "ID card",
            "document_number": "999999999",
            "document_date": "2017-06-06",
            "document_authority": "ČESKÁ REPUBLIKA",
            "nationality": "CZ",
            "gender": "F",
            "address_street": "VZOROVÁ 1",
            "address_zip": None,
            "address_city": "PRAHA",
            "address_country": "CZ",
            "images": [
                {
                    "image_index": 0,
                    "clockwise_rotation": 90,
                    "document_box": [100, 100, 900, 900],
                    "portrait_box": [50, 50, 300, 300],
                    "portrait_clockwise_rotation": 0,
                },
                {
                    "image_index": 1,
                    "clockwise_rotation": 270,
                    "document_box": [50, 50, 950, 950],
                    "portrait_box": None,
                    "portrait_clockwise_rotation": None,
                },
            ],
        }
        extraction.update(overrides)
        return extraction

    def test_scan_does_not_mutate_uploaded_documents(self):
        """Regression test: re-scanning must not alter the source images.

        The crafted extraction below carries a rotation and a tight document_box
        for each image. If the scan still wrote a rotated/cropped derivative back
        into ``x_id_document_front``/``x_id_document_back`` (the previous
        behaviour), the stored bytes would change here -- which is exactly why
        repeated scans used to drift further apart with every click: each scan
        fed the next one an already-degraded image instead of the original photo.
        """
        original_front = self.partner.x_id_document_front
        original_back = self.partner.x_id_document_back

        with patch.object(type(self.partner), "_call_id_scan", return_value=self._extraction()):
            self.partner.action_scan_id_documents()

        self.assertEqual(self.partner.x_id_document_front, original_front)
        self.assertEqual(self.partner.x_id_document_back, original_back)

        # A second scan must start from the same (still untouched) source.
        with patch.object(type(self.partner), "_call_id_scan", return_value=self._extraction()):
            self.partner.action_scan_id_documents()

        self.assertEqual(self.partner.x_id_document_front, original_front)
        self.assertEqual(self.partner.x_id_document_back, original_back)

    def test_scan_populates_processed_images(self):
        self.assertFalse(self.partner.x_id_document_front_processed)
        self.assertFalse(self.partner.x_id_document_back_processed)

        with patch.object(type(self.partner), "_call_id_scan", return_value=self._extraction()):
            self.partner.action_scan_id_documents()

        self.assertTrue(self.partner.x_id_document_front_processed)
        self.assertTrue(self.partner.x_id_document_back_processed)
        # The processed fields are derived from the (untouched) originals, so a
        # second scan may safely overwrite them again without error.
        with patch.object(type(self.partner), "_call_id_scan", return_value=self._extraction()):
            self.partner.action_scan_id_documents()
        self.assertTrue(self.partner.x_id_document_front_processed)
        self.assertTrue(self.partner.x_id_document_back_processed)

    def test_scan_sends_both_images_in_a_single_call(self):
        with patch.object(type(self.partner), "_call_id_scan", return_value=self._extraction()) as call_id_scan:
            self.partner.action_scan_id_documents()

        self.assertEqual(call_id_scan.call_count, 1)
        images = call_id_scan.call_args.args[0]
        self.assertEqual(len(images), 2)
        self.assertEqual({image["field_name"] for image in images}, {"x_id_document_front", "x_id_document_back"})

    def test_scan_applies_extracted_fields(self):
        with patch.object(type(self.partner), "_call_id_scan", return_value=self._extraction()):
            self.partner.action_scan_id_documents()

        if "firstname" in self.partner._fields and "lastname" in self.partner._fields:
            self.assertEqual(self.partner.firstname, "Anna")
            self.assertEqual(self.partner.lastname, "Vzorová")
        else:
            self.assertEqual(self.partner.name, "Anna Vzorová")
        self.assertEqual(self.partner.x_document_number, "999999999")
        self.assertEqual(self.partner.x_nationality.code, "CZ")
        self.assertEqual(self.partner.gender, "female")

    def test_scan_raises_without_any_usable_data(self):
        empty_extraction = {
            "first_name": None,
            "last_name": None,
            "birth_date": None,
            "document_type": None,
            "document_number": None,
            "document_date": None,
            "document_authority": None,
            "nationality": None,
            "gender": None,
            "address_street": None,
            "address_zip": None,
            "address_city": None,
            "address_country": None,
            "images": [],
        }
        with patch.object(type(self.partner), "_call_id_scan", return_value=empty_extraction):
            with self.assertRaises(UserError):
                self.partner.action_scan_id_documents()

    def test_scan_requires_at_least_one_image(self):
        partner = self.env["res.partner"].create({"name": "No Documents Yet", "company_type": "person"})
        with self.assertRaises(UserError):
            partner.action_scan_id_documents()


@tagged("post_install", "-at_install")
class TestParseExtractedDate(TransactionCase):
    def test_parses_known_formats(self):
        from ..models.res_partner import _parse_extracted_date

        self.assertEqual(_parse_extracted_date("2017-06-06").isoformat(), "2017-06-06")
        self.assertEqual(_parse_extracted_date("06.06.2017").isoformat(), "2017-06-06")
        self.assertEqual(_parse_extracted_date("06/06/2017").isoformat(), "2017-06-06")

    def test_rejects_unparseable_or_empty_values(self):
        from ..models.res_partner import _parse_extracted_date

        self.assertFalse(_parse_extracted_date(None))
        self.assertFalse(_parse_extracted_date(""))
        self.assertFalse(_parse_extracted_date("not a date"))


@tagged("post_install", "-at_install")
class TestNormalizedCropBox(TransactionCase):
    def test_scales_box_to_image_size(self):
        from ..models.res_partner import ResPartner

        # Box is in [top, left, bottom, right] permille order.
        box = ResPartner._normalized_crop_box([0, 0, 500, 1000], (200, 100))
        self.assertEqual(box, (0, 0, 200, 50))

    def test_rejects_malformed_boxes(self):
        from ..models.res_partner import ResPartner

        self.assertFalse(ResPartner._normalized_crop_box(None, (200, 100)))
        self.assertFalse(ResPartner._normalized_crop_box([0, 0, 500], (200, 100)))
        self.assertFalse(ResPartner._normalized_crop_box([500, 0, 0, 1000], (200, 100)))
