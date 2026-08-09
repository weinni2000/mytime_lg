import base64
import json
import logging
from datetime import datetime
from io import BytesIO

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
    GEMINI_DOCUMENT_TYPES,
    GEMINI_GENDER_SELECTION,
    GEMINI_GENDER_TITLES,
    GEMINI_ID_SCAN_PROMPT,
    GEMINI_ID_SCAN_SCHEMA,
    GEMINI_ID_SCAN_USER_PROMPT,
    GEMINI_MODEL,
    GEMINI_SCAN_MAX_DIMENSION,
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


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_id_document_front = fields.Image(string="ID Document Front")
    x_id_document_back = fields.Image(string="ID Document Back")

    def action_scan_id_documents(self):
        self.ensure_one()
        if not self.x_id_document_front and not self.x_id_document_back:
            raise UserError(_("Upload a front or back image of the document first."))
        try:
            images = self._prepare_id_scan_images()
            extraction = self._call_gemini_id_scan(images)
            self._apply_id_scan_images(extraction.get("images", []), images)
        except (UserError, ValueError, KeyError, IndexError, UnidentifiedImageError) as error:
            _logger.warning("ID document scan failed for %s: %s", self.display_name, error)
            raise UserError(_("Document scan failed: %(error)s", error=str(error))) from error
        self._apply_id_scan_extraction(extraction)
        return True

    def _prepare_id_scan_images(self):
        """Decode images and apply trustworthy EXIF orientation before vision analysis."""
        images = []
        for field_name in ("x_id_document_front", "x_id_document_back"):
            value = self[field_name]
            if not value:
                continue
            image = ImageOps.exif_transpose(Image.open(BytesIO(base64.b64decode(value))))
            image.load()
            images.append({"field_name": field_name, "image": image})
        return images

    def _call_gemini_id_scan(self, images=None):
        self.ensure_one()
        files = []
        images = images or self._prepare_id_scan_images()
        for image_data in images:
            scan_image = image_data["image"].copy()
            scan_image.thumbnail((GEMINI_SCAN_MAX_DIMENSION, GEMINI_SCAN_MAX_DIMENSION), Image.Resampling.LANCZOS)
            raw = self._encode_pil_image(scan_image)
            files.append({"mimetype": "image/jpeg", "value": base64.b64encode(raw).decode("ascii")})

        service = LLMApiService(self.env, provider="google")
        responses = service.request_llm(
            llm_model=GEMINI_MODEL,
            system_prompts=[GEMINI_ID_SCAN_PROMPT],
            user_prompts=[GEMINI_ID_SCAN_USER_PROMPT],
            files=files,
            schema=GEMINI_ID_SCAN_SCHEMA,
            temperature=0,
        )
        if not responses:
            raise UserError(_("Gemini did not return any data."))
        return json.loads(responses[0])

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

    def _apply_id_scan_images(self, analyses, images):
        """Make document images upright and use the best detected holder portrait."""
        analyses_by_index = {
            analysis.get("image_index"): analysis for analysis in analyses if isinstance(analysis, dict)
        }
        values = {}
        portrait_candidates = []
        for index, image_data in enumerate(images):
            analysis = analyses_by_index.get(index, {})
            rotation = analysis.get("clockwise_rotation", 0)
            if rotation not in (0, 90, 180, 270):
                rotation = 0
            original = image_data["image"]
            document = original
            document_box = self._normalized_crop_box(analysis.get("document_box"), original.size, 0.01)
            if document_box:
                document = original.crop(document_box)
            upright = self._rotate_clockwise(document, rotation)
            upright.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
            values[image_data["field_name"]] = base64.b64encode(self._encode_pil_image(upright))

            crop_box = self._normalized_crop_box(analysis.get("portrait_box"), original.size, 0.06)
            if not crop_box:
                continue
            portrait_rotation = analysis.get("portrait_clockwise_rotation")
            if portrait_rotation not in (0, 90, 180, 270):
                portrait_rotation = rotation
            portrait = self._rotate_clockwise(original.crop(crop_box), portrait_rotation)
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
