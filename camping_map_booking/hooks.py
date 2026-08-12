from odoo.exceptions import UserError

REQUIRED_INDUSTRY_MODULES = "campsite"  # , "industry_real_estate"


def pre_init_hook(env):
    installed = (
        env["ir.module.module"]
        .search([("name", "in", REQUIRED_INDUSTRY_MODULES), ("state", "=", "installed")])
        .mapped("name")
    )
    missing = [name for name in REQUIRED_INDUSTRY_MODULES if name not in installed]
    if missing:
        raise UserError(
            env._(
                "The following industry module(s) must be installed through the"
                " Apps UI (Industries wizard) before installing Camping Map"
                " Booking: %(modules)s. They cannot be installed automatically"
                " as dependencies."
            )
            % {"modules": ", ".join(missing)}
        )
