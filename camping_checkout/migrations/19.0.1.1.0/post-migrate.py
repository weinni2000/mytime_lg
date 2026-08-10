from odoo import SUPERUSER_ID, api

from ...hooks import _reorder_cart_step, _setup_pitch_step


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _setup_pitch_step(env)
    _reorder_cart_step(env)
