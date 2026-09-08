from pathlib import Path

from .models._const import DEFAULT_FLOWER_LARGE_PRICE, DEFAULT_FLOWER_SMALL_PRICE

_ENV_PATH = Path(__file__).parent / "misc" / ".env"


def _read_env_value(key):
    if not _ENV_PATH.exists():
        return False
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return False


def post_init_hook(env):
    company_ids = env["res.company"].search([])  # pylint: disable=no-search-all
    company_ids.write(
        {
            "default_flower_small": DEFAULT_FLOWER_SMALL_PRICE,
            "default_flower_large": DEFAULT_FLOWER_LARGE_PRICE,
        }
    )
    openrouter_key = _read_env_value("OPENROUTER")
    if openrouter_key:
        env["ir.config_parameter"].sudo().set_param("flower_calculator.openrouter_api_key", openrouter_key)
