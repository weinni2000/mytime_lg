import base64
import functools
import json
import logging
import os
from datetime import datetime
from io import BytesIO

import cv2
import numpy as np
import pytesseract
import requests
from markupsafe import Markup
from PIL import Image, ImageOps, UnidentifiedImageError

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.city_tax.models._const import (
    _DESKLINE_SALUTATION_FRAU,
    _DESKLINE_SALUTATION_HERR,
)

from ._const import (
    CLAUDE_MODEL,
    GEMINI_DOCUMENT_TYPES,
    GEMINI_GENDER_SELECTION,
    GEMINI_GENDER_TITLES,
    GEMINI_ID_SCAN_PROMPT,
    GEMINI_ID_SCAN_SCHEMA,
    GEMINI_ID_SCAN_USER_PROMPT,
    GEMINI_MODEL,
    GEMINI_SCAN_MAX_DIMENSION,
    OPENAI_FALLBACK_MODEL,
)

_logger = logging.getLogger(__name__)

_IMAGE_SIGNATURES = (
    (b"\x89PNG", "image/png"),
    (b"\xff\xd8", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)

_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d")

_GEMINI_GENDER_ANREDE = {"M": _DESKLINE_SALUTATION_HERR, "F": _DESKLINE_SALUTATION_FRAU}

_DOCUMENT_BOX_MIN_AREA_RATIO = 0.2
_DOCUMENT_BOX_MAX_AREA_RATIO = 0.85
_DOCUMENT_BOX_MARGIN_RATIO = 0.02
# ID cards and driving licences are ID-1 format (~1.586:1); an open passport
# spread is closer to 2:1. This range is generous enough for perspective
# distortion in a hand-held photo while still rejecting background clutter
# (floor tiles, door frames, ...) that happens to form a rectangle.
_DOCUMENT_BOX_ASPECT_RATIO_RANGE = (1.3, 2.3)

_FACE_DETECTOR_MODEL_PATH = os.path.join(os.path.dirname(__file__), "face_detection_yunet_2023mar.onnx")
_FACE_DETECTION_MIN_SCORE = 0.7
# (left, top, right, bottom), as a ratio of the detected face box's width/height.
# Tuned against a real ID photo: margins much larger than this end up including
# surrounding printed text instead of just the holder's photo.
_FACE_CROP_MARGIN_RATIO = (0.25, 0.35, 0.25, 0.35)


@functools.lru_cache(maxsize=1)
def _get_face_detector():
    """Load the YuNet face detector once per worker process."""
    return cv2.FaceDetectorYN_create(
        _FACE_DETECTOR_MODEL_PATH, "", (0, 0), score_threshold=_FACE_DETECTION_MIN_SCORE
    )


def _detect_document_box(image):
    """Best-effort local detection of the ID document's rectangle in a photo.

    Runs before the image is sent to the vision model, so a tight crop reduces
    background clutter and reliance on the model's own framing. Returns an
    axis-aligned ``(left, top, right, bottom)`` box, or ``None`` when no
    confident rectangle is found (e.g. a cluttered background, low contrast,
    or a fingers-occluded card breaking up its own outline), so the caller
    falls back to the untouched photo rather than risk cropping out the
    document itself -- a hand-held photo's background (a wood floor, a door)
    can otherwise form a large, clean quadrilateral that outranks the card.
    """
    grayscale = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    edges = cv2.dilate(cv2.Canny(cv2.GaussianBlur(grayscale, (5, 5), 0), 50, 150), None, iterations=2)
    contours, _hierarchy = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    image_area = image.width * image.height
    best_box, best_area = None, 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area <= best_area or not (
            image_area * _DOCUMENT_BOX_MIN_AREA_RATIO <= area <= image_area * _DOCUMENT_BOX_MAX_AREA_RATIO
        ):
            continue
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        x, y, width, height = cv2.boundingRect(approx)
        if width == 0 or height == 0:
            continue
        aspect_ratio = max(width, height) / min(width, height)
        if not (_DOCUMENT_BOX_ASPECT_RATIO_RANGE[0] <= aspect_ratio <= _DOCUMENT_BOX_ASPECT_RATIO_RANGE[1]):
            continue
        best_box, best_area = (x, y, x + width, y + height), area
    return best_box


def _crop_to_document(image):
    """Locally tighten a photo to the detected document, with a small margin."""
    box = _detect_document_box(image)
    if not box:
        return image
    left, top, right, bottom = box
    margin_x = (right - left) * _DOCUMENT_BOX_MARGIN_RATIO
    margin_y = (bottom - top) * _DOCUMENT_BOX_MARGIN_RATIO
    return image.crop(
        (
            max(0, round(left - margin_x)),
            max(0, round(top - margin_y)),
            min(image.width, round(right + margin_x)),
            min(image.height, round(bottom + margin_y)),
        )
    )


_TEXT_ROTATION_MIN_CONFIDENCE = 1.0


def _detect_text_rotation(image):
    """Best-effort local text-orientation detection via Tesseract OSD.

    More reliable than asking the vision model to judge orientation, and
    works on both sides of the document (unlike face detection, which only
    helps on the side carrying the holder's photo). Returns the clockwise
    rotation (0/90/180/270) needed to make the image's text upright, or
    ``None`` when Tesseract can't find enough text to be confident (a blurry
    photo, a mostly-graphical side, too few characters, ...).
    """
    try:
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractError:
        return None
    if osd.get("orientation_conf", 0) < _TEXT_ROTATION_MIN_CONFIDENCE:
        return None
    return int(osd["rotate"]) % 360


def _guess_image_mimetype(raw):
    for signature, mimetype in _IMAGE_SIGNATURES:
        if raw.startswith(signature):
            return mimetype
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _parse_extracted_date(value):
    if not value or not isinstance(value, str):
        return False
    value = value.strip()
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    _logger.warning("Could not parse date %r returned by the document scan.", value)
    return False


_PROCESSED_FIELD_BY_SOURCE = {
    "x_id_document_front": "x_id_document_front_processed",
    "x_id_document_back": "x_id_document_back_processed",
}


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_id_document_front = fields.Image(string="ID Document Front")
    x_id_document_back = fields.Image(string="ID Document Back")
    x_id_document_front_processed = fields.Image(
        string="ID Document Front (Processed)",
        help="Upright, cropped version produced by the last scan. The original above is never modified.",
    )
    x_id_document_back_processed = fields.Image(
        string="ID Document Back (Processed)",
        help="Upright, cropped version produced by the last scan. The original above is never modified.",
    )
    x_show_all = fields.Boolean(
        string="Show All Images",
        help="Show the original, as-uploaded photos alongside the processed ones.",
    )

    def action_scan_id_documents(self):
        self.ensure_one()
        if not self.x_id_document_front and not self.x_id_document_back:
            raise UserError(_("Upload a front or back image of the document first."))
        # Serialize concurrent scans of the same partner (e.g. an impatient double
        # click): without this, two overlapping requests can interleave their
        # writes and leave the record in a mix of both results.
        self.env.cr.execute("SELECT id FROM res_partner WHERE id = %s FOR UPDATE", [self.id])
        try:
            images = self._prepare_id_scan_images()
            extraction = self._call_id_scan(images)
            self._apply_id_scan_images(extraction.get("images", []), images)
        except (UserError, ValueError, KeyError, IndexError, UnidentifiedImageError) as error:
            _logger.warning("ID document scan failed for %s: %s", self.display_name, error)
            raise UserError(_("Document scan failed: %(error)s", error=str(error))) from error
        self._apply_id_scan_extraction(extraction)
        return True

    def _prepare_id_scan_images(self):
        """Decode images, apply trustworthy EXIF orientation, and locally crop
        each one to the detected document before it is sent for vision analysis.

        ``image`` keeps the untouched, as-uploaded photo; ``scan_image`` is the
        (possibly cropped) version actually sent to and referenced by the model.
        """
        images = []
        for field_name in ("x_id_document_front", "x_id_document_back"):
            value = self[field_name]
            if not value:
                continue
            image = ImageOps.exif_transpose(Image.open(BytesIO(base64.b64decode(value))))
            image.load()
            images.append({"field_name": field_name, "image": image, "scan_image": _crop_to_document(image)})
        return images

    def _call_id_scan(self, images=None):
        self.ensure_one()
        files = []
        images = images or self._prepare_id_scan_images()
        for image_data in images:
            scan_image = image_data["scan_image"].copy()
            scan_image.thumbnail((GEMINI_SCAN_MAX_DIMENSION, GEMINI_SCAN_MAX_DIMENSION), Image.Resampling.LANCZOS)
            raw = self._encode_pil_image(scan_image)
            files.append({"mimetype": "image/jpeg", "value": base64.b64encode(raw).decode("ascii")})

        request_values = {
            "system_prompts": [GEMINI_ID_SCAN_PROMPT],
            "user_prompts": [GEMINI_ID_SCAN_USER_PROMPT],
            "files": files,
            "schema": GEMINI_ID_SCAN_SCHEMA,
            "temperature": 0,
        }
        provider = self.env.company.id_scan_provider
        if provider == "anthropic":
            return self._call_claude_id_scan(files)
        model = GEMINI_MODEL if provider == "google" else OPENAI_FALLBACK_MODEL
        responses = LLMApiService(self.env, provider=provider).request_llm(
            llm_model=model,
            **request_values,
        )
        if not responses:
            raise UserError(_("The document scanning service did not return any data."))
        return json.loads(responses[0])

    def _call_claude_id_scan(self, files):
        api_key = self.env["ir.config_parameter"].sudo().get_param("ai.anthropic_key") or os.getenv(
            "ANTHROPIC_API_KEY"
        )
        if not api_key:
            raise UserError(_("No API key set for provider 'anthropic'"))

        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": file["mimetype"],
                    "data": file["value"],
                },
            }
            for file in files
        ]
        content.append({"type": "text", "text": GEMINI_ID_SCAN_USER_PROMPT})
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                    "x-api-key": api_key,
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 2048,
                    "temperature": 0,
                    "system": GEMINI_ID_SCAN_PROMPT,
                    "messages": [{"role": "user", "content": content}],
                    "output_config": {
                        "format": {
                            "type": "json_schema",
                            "schema": GEMINI_ID_SCAN_SCHEMA,
                        }
                    },
                },
                timeout=60,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            response = getattr(error, "response", None)
            try:
                message = response.json().get("error", {}).get("message") if response is not None else None
            except ValueError:
                message = response.text
            raise UserError(message or str(error)) from error

        result = response.json()
        text_blocks = [block.get("text") for block in result.get("content", []) if block.get("type") == "text"]
        if not text_blocks:
            raise UserError(_("Claude did not return any data."))
        return json.loads(text_blocks[0])

    @staticmethod
    def _encode_pil_image(image):
        output = BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=92, optimize=True)
        return output.getvalue()

    @staticmethod
    def _rotate_clockwise(image, degrees):
        return image.rotate(-degrees, expand=True) if degrees else image.copy()

    @staticmethod
    def _normalized_crop_box(box, image_size, margin_ratio=0):
        if not isinstance(box, list) or len(box) != 4:
            return False
        if not all(isinstance(value, int | float) for value in box):
            return False
        top, left, bottom, right = box
        width, height = image_size
        left, right = left * width / 1000, right * width / 1000
        top, bottom = top * height / 1000, bottom * height / 1000
        if right <= left or bottom <= top:
            return False
        margin_x = (right - left) * margin_ratio
        margin_y = (bottom - top) * margin_ratio
        return (
            max(0, round(left - margin_x)),
            max(0, round(top - margin_y)),
            min(width, round(right + margin_x)),
            min(height, round(bottom + margin_y)),
        )

    def _detect_upright_face(self, image):
        """Return a reliable upright rotation and portrait crop, if detected.

        Uses YuNet, a small DNN face detector (see ``_get_face_detector``),
        rather than a Haar cascade: on a real ID photo, the cascade's own
        area-weighted scoring picked a false-positive "face" match on the
        printed name/text over the actual, more confidently detected photo,
        because it favoured box size over detection confidence. YuNet's score
        is a proper detection confidence, is far less prone to matching text,
        and lets candidates be ranked by confidence alone.
        """
        detector = _get_face_detector()
        candidates = []
        for rotation in (0, 90, 180, 270):
            rotated = self._rotate_clockwise(image, rotation)
            array = cv2.cvtColor(np.asarray(rotated.convert("RGB")), cv2.COLOR_RGB2BGR)
            detector.setInputSize((array.shape[1], array.shape[0]))
            _retval, faces = detector.detect(array)
            for face in () if faces is None else faces:
                left, top, width, height = face[:4].astype(int)
                score = float(face[14])
                if width <= 0 or height <= 0 or score < _FACE_DETECTION_MIN_SCORE:
                    continue
                candidates.append((score, rotation, rotated, left, top, width, height))
        if not candidates:
            return False

        _, rotation, rotated, left, top, width, height = max(candidates, key=lambda item: item[0])
        portrait_box = (
            max(0, round(left - width * _FACE_CROP_MARGIN_RATIO[0])),
            max(0, round(top - height * _FACE_CROP_MARGIN_RATIO[1])),
            min(rotated.width, round(left + width * (1 + _FACE_CROP_MARGIN_RATIO[2]))),
            min(rotated.height, round(top + height * (1 + _FACE_CROP_MARGIN_RATIO[3]))),
        )
        return rotation, rotated.crop(portrait_box)

    def _apply_id_scan_images(self, analyses, images):
        """Store an upright, document-cropped version of each scan for display,
        and set the partner avatar from the best detected holder portrait.

        The uploaded document images (``x_id_document_front``/``x_id_document_back``)
        are never modified here: they are the source of truth for the identity
        record, and re-scanning must always start from the same original photos
        for results to stay reproducible across repeated scans. The *_processed
        fields are safe to overwrite on every scan since they are always derived
        from those untouched originals, never from each other.
        """
        analyses_by_index = {
            analysis.get("image_index"): analysis for analysis in analyses if isinstance(analysis, dict)
        }
        values = {}
        portrait_candidates = []
        for index, image_data in enumerate(images):
            analysis = analyses_by_index.get(index, {})
            scan_image = image_data["scan_image"]

            document = scan_image
            document_box = self._normalized_crop_box(analysis.get("document_box"), scan_image.size, 0.01)
            if document_box:
                document = scan_image.crop(document_box)

            # Prefer local signals over the model's own orientation guess: a
            # detected face is unambiguous, and Tesseract reads the printed
            # text directly, whereas the model has been observed to get the
            # rotation wrong (e.g. reporting a document as upright when it is
            # actually upside down).
            detected_face = self._detect_upright_face(scan_image)
            if detected_face:
                rotation, portrait = detected_face
                portrait_candidates.append((portrait.width * portrait.height, portrait))
            else:
                rotation = _detect_text_rotation(document)
                if rotation is None:
                    rotation = analysis.get("clockwise_rotation", 0)
                if rotation not in (0, 90, 180, 270):
                    rotation = 0

            upright = self._rotate_clockwise(document, rotation)
            if upright.height > upright.width:
                rotation = (rotation + 90) % 360
                upright = self._rotate_clockwise(document, rotation)
            upright.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
            processed_field_name = _PROCESSED_FIELD_BY_SOURCE[image_data["field_name"]]
            values[processed_field_name] = base64.b64encode(self._encode_pil_image(upright))

            if detected_face:
                continue
            crop_box = self._normalized_crop_box(analysis.get("portrait_box"), upright.size, 0.06)
            if not crop_box:
                continue
            portrait = upright.crop(crop_box)
            portrait_candidates.append((portrait.width * portrait.height, portrait))

        if portrait_candidates:
            portrait = max(portrait_candidates, key=lambda candidate: candidate[0])[1]
            values["image_1920"] = base64.b64encode(self._encode_pil_image(portrait))
        self.write(values)

    def _find_country_by_code(self, code):
        """Look up a country by its ISO 3166-1 alpha-2 code.

        ``res.country.name`` is translated, so matching Gemini's output against it
        fails for non-English users (e.g. "Italy" never matches "Italien"). The
        ``code`` field is language-independent, so we match on that instead.
        """
        if not code or not isinstance(code, str):
            return False
        return self.env["res.country"].search([("code", "=", code.strip().upper())], limit=1)

    def _apply_id_scan_extraction(self, extraction):  # noqa: C901
        self.ensure_one()
        values = {}

        first_name = (extraction.get("first_name") or "").strip()
        last_name = (extraction.get("last_name") or "").strip()
        if first_name or last_name:
            if "firstname" in self._fields and "lastname" in self._fields:
                if first_name:
                    values["firstname"] = first_name
                if last_name:
                    values["lastname"] = last_name
            else:
                values["name"] = " ".join(part for part in (first_name, last_name) if part)

        birth_date = _parse_extracted_date(extraction.get("birth_date"))
        if birth_date:
            values["birthdate_date"] = birth_date

        document_type = extraction.get("document_type")
        if document_type in GEMINI_DOCUMENT_TYPES:
            values["x_document_type"] = document_type

        document_number = extraction.get("document_number")
        if document_number:
            values["x_document_number"] = document_number

        document_date = _parse_extracted_date(extraction.get("document_date"))
        if document_date:
            values["x_document_date"] = document_date

        document_authority = extraction.get("document_authority")
        if document_authority:
            values["x_document_authority"] = document_authority

        nationality = self._find_country_by_code(extraction.get("nationality"))
        if nationality:
            values["x_nationality"] = nationality.id

        address_street = extraction.get("address_street")
        if address_street:
            values["street"] = address_street

        address_zip = extraction.get("address_zip")
        if address_zip:
            values["zip"] = address_zip

        address_city = extraction.get("address_city")
        if address_city:
            values["city"] = address_city

        address_country = self._find_country_by_code(extraction.get("address_country"))
        if address_country:
            values["country_id"] = address_country.id

        gender_code = extraction.get("gender")

        gender_value = GEMINI_GENDER_SELECTION.get(gender_code)
        if gender_value:
            values["gender"] = gender_value

        title_name = GEMINI_GENDER_TITLES.get(gender_code)
        if title_name:
            title = self.env["res.partner.title"].search([("name", "=", title_name)], limit=1)
            if title:
                values["title_id"] = title.id

        anrede = _GEMINI_GENDER_ANREDE.get(gender_code)
        if anrede:
            values["x_anrede"] = anrede

        if not values:
            raise UserError(_("Could not read any information from the uploaded document(s)."))

        self.write(values)
        self._log_id_scan_chatter(list(values.keys()))

    def _log_id_scan_chatter(self, field_names):
        self.ensure_one()
        descriptions = self.fields_get(field_names, attributes=["selection", "type"])
        lines = []
        for field_name in field_names:
            field = self._fields[field_name]
            value = self[field_name]
            if field.type == "many2one":
                display_value = value.display_name if value else ""
            elif field.type == "selection":
                display_value = dict(descriptions[field_name]["selection"]).get(value, value)
            elif field.type in ("date", "datetime"):
                display_value = value.isoformat() if value else ""
            else:
                display_value = value
            lines.append(Markup("<li>%s: %s</li>") % (field.string, str(display_value)))
        body = Markup("%s<ul>%s</ul>") % (_("ID document scan updated:"), Markup("").join(lines))
        self.message_post(body=body)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    partner_image_128 = fields.Image(related="partner_id.image_128", readonly=True)
