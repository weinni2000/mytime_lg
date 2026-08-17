import re

_CONTEXTUAL_CODE_PATTERNS = (
    re.compile(
        r"(?:booking(?:\.com)?|sicherheitscode|best(?:ä|ae)tigungscode|verification\s+code)"
        r"[^0-9]{0,80}([0-9](?:[ -]?[0-9]){3,7})(?![0-9])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:code|pin|otp)\s*(?:lautet|is|:)?\s*([0-9](?:[ -]?[0-9]){3,7})(?![0-9])",
        re.IGNORECASE,
    ),
)
_STANDALONE_CODE_RE = re.compile(r"(?<![0-9])([0-9]{4,8})(?![0-9])")


def extract_booking_code(message):
    """Return a 4-8 digit verification code extracted from an SMS message."""
    if not isinstance(message, str):
        return False

    normalized_message = " ".join(message.split())
    for pattern in _CONTEXTUAL_CODE_PATTERNS:
        match = pattern.search(normalized_message)
        if match:
            code = re.sub(r"\D", "", match.group(1))
            if 4 <= len(code) <= 8:
                return code

    match = _STANDALONE_CODE_RE.search(normalized_message)
    return match.group(1) if match else False
