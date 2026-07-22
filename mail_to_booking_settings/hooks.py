import os
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


def post_init_hook(env):
    if not DEEPSEEK_API_KEY:
        return
    company_ids = env["res.company"].sudo().search([])  # pylint: disable=no-search-all
    company_ids.write({"deepseek_api_key": DEEPSEEK_API_KEY})
