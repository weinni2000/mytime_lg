from odoo import SUPERUSER_ID, api

# Migration scripts are loaded standalone (not as package members), so a
# relative import would fail at runtime; absolute import is required here.
from odoo.addons.planning_gantt_view_mode_oca.hooks import (  # noqa: E501 pylint: disable=odoo-addons-relative-import
    _ensure_timeline_view,
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _ensure_timeline_view(env)
