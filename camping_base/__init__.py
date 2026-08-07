from . import models


def post_init_hook(env):
    camping_tag = env.ref("camping_base.ir_cron_tag_camping")
    cron_xmlids = (
        "camping_additional_fields_base.ir_cron_sale_order_update_is_ongoing",
        "camping_automation.ir_cron_camping_guesty_import",
        "mytime_pitchup_sync.ir_cron_pitchup_order_sync",
        "whatsapp_private.ir_cron_private_whatsapp_listener",
        "whatsapp_private.ir_cron_private_whatsapp_contact_sync",
    )
    crons = env["ir.cron"]
    for xmlid in cron_xmlids:
        cron = env.ref(xmlid, raise_if_not_found=False)
        if cron:
            crons |= cron
    crons.write({"tag_ids": [(4, camping_tag.id)]})
