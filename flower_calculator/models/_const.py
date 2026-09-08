import copy

FLOWER_CALCULATOR_MODEL = "gpt-4.1"

FLOWER_OPENROUTER_MODEL = "google/gemini-2.5-flash"
FLOWER_OPENROUTER_MODEL_PRO = "google/gemini-2.5-pro"
FLOWER_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

FLOWER_MODEL_SELECTION = [
    ("gpt-4.1-mini", "GPT-4.1 Mini"),
    ("gpt-4.1", "GPT-4.1"),
    ("gpt-4o", "GPT-4o"),
    ("gpt-5-mini", "GPT-5 Mini"),
    ("gpt-5", "GPT-5"),
    (FLOWER_OPENROUTER_MODEL, "Gemini 2.5 Flash (OpenRouter)"),
    (FLOWER_OPENROUTER_MODEL_PRO, "Gemini 2.5 Pro (OpenRouter)"),
]

# Gemini would be the better-suited model for the bounding-box detection
# feature (Google explicitly supports/documents object detection with
# normalized coordinates), but Google's own Generative Language API rejects
# requests from this server's location ("User location is not supported for
# the API use."). Routed through OpenRouter instead, Gemini is reachable
# (OpenRouter proxies through its own infrastructure/credentials), so that
# is offered as a separate "openrouter" provider alongside the OpenAI ones.
FLOWER_MODEL_PROVIDERS = {
    "gpt-4.1-mini": "openai",
    "gpt-4.1": "openai",
    "gpt-4o": "openai",
    "gpt-5-mini": "openai",
    "gpt-5": "openai",
    FLOWER_OPENROUTER_MODEL: "openrouter",
    FLOWER_OPENROUTER_MODEL_PRO: "openrouter",
}

FLOWER_ANNOTATION_COLORS = [
    (220, 20, 60),  # crimson
    (0, 102, 255),  # blue
    (0, 153, 51),  # green
    (255, 140, 0),  # orange
    (153, 0, 204),  # purple
    (255, 0, 153),  # magenta
    (0, 204, 204),  # teal
    (204, 153, 0),  # gold
    (0, 51, 102),  # navy
    (102, 51, 0),  # brown
]

FLOWER_PRODUCT_CATEGORY_COMPLETE_NAME = "All / Lisi Grün / Urproduktion / Blumen"

DEFAULT_FLOWER_SMALL_PRICE = 0.50
DEFAULT_FLOWER_LARGE_PRICE = 2.00

FLOWER_COUNTER_MODE_INTERNAL = "internal"
FLOWER_COUNTER_MODE_DEFAULT = "default"

FLOWER_COUNTER_MODE_STEMS = "stems"

FLOWER_COUNTER_MODE_SELECTION = [
    (FLOWER_COUNTER_MODE_DEFAULT, "Default"),
    (FLOWER_COUNTER_MODE_INTERNAL, "Only Internal Flowers"),
    (FLOWER_COUNTER_MODE_STEMS, "Count Stems"),
]

FLOWER_CALCULATOR_TAXONOMY_INSTRUCTIONS = (
    "For each item also provide, whenever you can determine them with "
    "confidence: the botanical genus in 'genus' (e.g. 'Lilium'), the "
    "German common name in 'german_name' (e.g. 'Lilie'), the group or type "
    "in 'group_type' (e.g. 'OT-Hybride (Oriental × Trompetenlilie)'), the "
    "variety or cultivar in 'variety' (e.g. 'Tisento'), and the color in "
    "'color' (e.g. 'Weiß'). Use null for any of these you cannot determine "
    "with confidence — never guess."
)

FLOWER_CALCULATOR_SYSTEM_PROMPT = (
    "You are a florist assistant that reads photos of flowers or floral "
    "arrangements. Identify every distinct type of plant material visible "
    "in the photo — flowers, grasses, seed pods, foliage/greenery, and any "
    "other decorative botanical item, not just blooms — and count how many "
    "stems of each type are present. Only report types you can actually "
    "see; never invent types that are not in the photo. Report every "
    "distinct type, including ones that are not in the product catalog "
    "below — never omit an item just because it has no catalog match; a "
    "bouquet often contains plant material we don't sell ourselves. For "
    "each item also classify its size as either 'small' (e.g. daisies, "
    "violets, baby's breath, grasses) or 'large' (e.g. roses, sunflowers, "
    "lilies); this is used to price it when it isn't in our product "
    "catalog. Also write a short description (variety/cultivar if you can "
    "tell, color, condition) in 'description'. " + FLOWER_CALCULATOR_TAXONOMY_INSTRUCTIONS + " "
    "You will also be given our product catalog as a list of 'database "
    "id: product name' entries. If an item exactly matches one catalog "
    "entry, set product_id to that entry's database id; otherwise set "
    "product_id to null. Never invent an id that is not in the catalog."
)

FLOWER_CALCULATOR_GARDENER_SYSTEM_PROMPT = (
    "You are an experienced gardener and florist describing a photo of "
    "flowers or a floral arrangement. Identify every distinct type of "
    "plant material you can see — flowers, grasses, seed pods, foliage/"
    "greenery, and any other decorative botanical item, not just blooms — "
    "and count how many stems of each type are present. Only report what "
    "you can actually see; never invent types that are not in the photo. "
    "For each item also classify its size as either 'small' (e.g. "
    "daisies, violets, baby's breath, grasses) or 'large' (e.g. roses, "
    "sunflowers, lilies). Write a detailed gardener's description for "
    "each one in 'description' — variety or cultivar if you can tell, "
    "color, bloom stage, and condition; be as detailed and precise as "
    "possible. " + FLOWER_CALCULATOR_TAXONOMY_INSTRUCTIONS + " Leave product_id null."
)

FLOWER_CALCULATOR_STEMS_SYSTEM_PROMPT = (
    "You are an experienced florist describing a photo of flowers or a "
    "floral arrangement. Florists buy, sell, and count flowers by the "
    "STEM, which is the usual trade unit — not by the individual flower "
    "head. A single stem can carry several flower heads (e.g. spray "
    "roses, spray carnations, branching Alstroemeria, multi-headed "
    "Dahlias, or a stem of baby's breath with dozens of tiny blooms); "
    "such a stem still counts as ONE, no matter how many heads it "
    "carries. Identify every distinct type of plant material you can "
    "see — flowers, grasses, seed pods, foliage/greenery, and any other "
    "decorative botanical item, not just blooms — and count the number of "
    "STEMS of each type, never the number of individual flower heads. "
    "Only report types you can actually see; never invent types that are "
    "not in the photo. For each item also classify its size as either "
    "'small' (e.g. daisies, violets, baby's breath, grasses) or 'large' "
    "(e.g. roses, sunflowers, lilies). Write a short description in "
    "'description', noting if it is a single-headed or multi-headed/spray "
    "stem. " + FLOWER_CALCULATOR_TAXONOMY_INSTRUCTIONS + " You will also be given our product "
    "catalog as a list of 'database id: product name' entries. If an item "
    "exactly matches one catalog entry, set product_id to that entry's "
    "database id; otherwise set product_id to null. Never invent an id that "
    "is not in the catalog. If asked to also "
    "return bounding-box detections, draw one box per whole stem — "
    "covering all of its flower heads together — never one box per "
    "individual flower head on a multi-headed stem."
)

FLOWER_CALCULATOR_USER_PROMPT = (
    "How many of each type of flower, grass, seed pod, foliage, and other "
    "plant material are shown in this photo?"
)

FLOWER_CALCULATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "flowers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "number"},
                    "size": {"type": "string", "enum": ["small", "large"]},
                    "product_id": {"type": ["integer", "null"]},
                    "description": {"type": ["string", "null"]},
                    "genus": {"type": ["string", "null"]},
                    "german_name": {"type": ["string", "null"]},
                    "group_type": {"type": ["string", "null"]},
                    "variety": {"type": ["string", "null"]},
                    "color": {"type": ["string", "null"]},
                },
                "required": [
                    "name",
                    "quantity",
                    "size",
                    "product_id",
                    "description",
                    "genus",
                    "german_name",
                    "group_type",
                    "variety",
                    "color",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["flowers"],
    "additionalProperties": False,
}

FLOWER_CALCULATOR_DETECTION_INSTRUCTIONS = (
    "Also return a 'detections' array: one entry for every individual "
    "flower, grass, seed pod, foliage sprig, or other plant item you can "
    "visually locate, not just one per type. Each entry has 'name', a "
    "bounding box as fractions of the image width/height (0.0 to 1.0, "
    "origin top-left): 'x_min', 'y_min', 'x_max', 'y_max', and a "
    "'confidence' score from 0.0 to 1.0 for how sure you are that the box "
    "is placed exactly on that item (1.0 = certain, 0.5 = rough guess, "
    "0.0 = you are not confident at all where it is). Be honest about "
    "confidence rather than defaulting to a high number. Try to provide "
    "one detection per physical item visible, matching the total counts "
    "above as closely as possible."
)

# Detections below this confidence are skipped when drawing the annotated
# photo - the model itself flags how sure it is about a box's placement,
# and low-confidence boxes are more often wrong than useful.
FLOWER_DETECTION_CONFIDENCE_THRESHOLD = 0.5

_FLOWER_DETECTION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "x_min": {"type": "number"},
            "y_min": {"type": "number"},
            "x_max": {"type": "number"},
            "y_max": {"type": "number"},
            "confidence": {"type": "number"},
        },
        "required": ["name", "x_min", "y_min", "x_max", "y_max", "confidence"],
        "additionalProperties": False,
    },
}


def get_flower_calculator_schema(include_detections):
    schema = copy.deepcopy(FLOWER_CALCULATOR_SCHEMA)
    if include_detections:
        schema["properties"]["detections"] = _FLOWER_DETECTION_SCHEMA
        schema["required"].append("detections")
    return schema
