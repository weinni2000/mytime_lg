GEMINI_MODEL = "gemini-2.5-flash"

# Longest side, in pixels, for images sent to Gemini. Large phone-camera photos
# (4000px+) are downsampled by the API anyway; sending them at that size just
# wastes bandwidth without helping text legibility, so cap them ourselves.
GEMINI_SCAN_MAX_DIMENSION = 1600

GEMINI_DOCUMENT_TYPES = ("Passport", "ID card", "Driving license")

GEMINI_GENDER_TITLES = {"M": "Mister", "F": "Madam"}
GEMINI_GENDER_SELECTION = {"M": "male", "F": "female"}

GEMINI_ID_SCAN_PROMPT = """You are an identity document reading assistant. You receive one or \
two images of the same identity document (front and/or back side of a passport, national ID \
card, or driving license) and must extract the holder's given name(s) and surname as separate \
first_name and last_name fields (a passport labels these "Given names"/"Surname"; keep any \
middle names with the first_name and never merge the two into one field), the date of birth, \
the document type, the document number, the document's issue date (not its expiry date), the \
issuing authority, the holder's sex as stated on the document, and the holder's nationality as \
an ISO 3166-1 alpha-2 country code (e.g. "IT" for Italy). Also look for the holder's registered \
address, which is often printed on the back of national ID cards: extract it as separate street \
(including house number), postal code, city, and country (as an ISO 3166-1 alpha-2 country \
code, e.g. "DE" for Germany) fields. Leave address \
fields null if no address is printed on the document. Also inspect every attached image: use \
its zero-based attachment order as \
image_index and report the clockwise rotation required to make the document upright. Report the \
document_box tightly enclosing only the physical document in the ORIGINAL attached image. When \
the image contains the holder's printed portrait, report its bounding box
in the ORIGINAL attached image. All bounding-box coordinates are integers
from 0 to 1000 in [top, left, bottom, right] order.
The box must tightly enclose only the portrait photograph, not text, borders,
signatures, holograms, or the whole document. Independently report the clockwise \
rotation required to make the person's face in that cropped portrait upright. For \
document_type, always choose the closest matching option even if you are not \
fully certain — never leave it empty. Leave any other field null if you cannot read it with \
confidence. Never invent data that is not present in the image(s)."""

GEMINI_ID_SCAN_USER_PROMPT = "Extract the identity document data from the attached image(s)."

GEMINI_ID_SCAN_SCHEMA = {
    "type": "object",
    "properties": {
        "first_name": {"type": ["string", "null"]},
        "last_name": {"type": ["string", "null"]},
        "birth_date": {"type": ["string", "null"]},
        "document_type": {"type": "string", "enum": list(GEMINI_DOCUMENT_TYPES)},
        "document_number": {"type": ["string", "null"]},
        "document_date": {"type": ["string", "null"]},
        "document_authority": {"type": ["string", "null"]},
        "nationality": {"type": ["string", "null"]},
        "gender": {"type": ["string", "null"], "enum": ["M", "F", None]},
        "address_street": {"type": ["string", "null"]},
        "address_zip": {"type": ["string", "null"]},
        "address_city": {"type": ["string", "null"]},
        "address_country": {"type": ["string", "null"]},
        "images": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "image_index": {"type": "integer"},
                    "clockwise_rotation": {"type": "integer", "enum": [0, 90, 180, 270]},
                    "document_box": {
                        "type": ["array", "null"],
                        "items": {"type": "integer"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "portrait_box": {
                        "type": ["array", "null"],
                        "items": {"type": "integer"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "portrait_clockwise_rotation": {
                        "type": ["integer", "null"],
                        "enum": [0, 90, 180, 270, None],
                    },
                },
                "required": [
                    "image_index",
                    "clockwise_rotation",
                    "document_box",
                    "portrait_box",
                    "portrait_clockwise_rotation",
                ],
            },
        },
    },
    "required": [
        "first_name",
        "last_name",
        "birth_date",
        "document_type",
        "document_number",
        "document_date",
        "document_authority",
        "nationality",
        "gender",
        "address_street",
        "address_zip",
        "address_city",
        "address_country",
        "images",
    ],
}
