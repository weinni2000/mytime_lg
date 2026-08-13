# Desired left-to-right order of the schedule action's view switcher. Whichever
# of these modes actually exists on the action is placed in this order; the rest
# are left untouched. gantt / gantt_maps stay first so the schedule keeps opening
# on the planning view and timeline never becomes the default.
_VIEW_ORDER = ["gantt_maps", "gantt", "timeline", "calendar", "list", "kanban", "form"]


def _ensure_timeline_view(env):
    """Add the timeline mode to the booking schedule action, idempotently.

    We deliberately do NOT reset ``view_ids`` (the ``(5, 0, 0)`` command) nor
    overwrite the scalar ``view_mode``: both booking_engine and gantt_maps also
    edit this same action, and resetting/overwriting made the modules clobber
    each other. ``_compute_views`` includes every ``act_window.view`` row
    regardless of ``view_mode``, so a row is all we need. Rows created via
    ``(0, 0, ...)`` have a NULL sequence which sorts *before* explicit ones, so
    we normalise the sequences to keep the ordering deterministic.
    """
    action = env.ref(
        "booking_engine.booking_engine_rooms_schedule_action",
        raise_if_not_found=False,
    )
    timeline_view = env.ref(
        "planning_gantt_view_mode_oca.booking_engine_planning_timeline_view",
        raise_if_not_found=False,
    )
    if not action or not timeline_view:
        return

    if not action.view_ids.filtered(lambda v: v.view_mode == "timeline"):
        env["ir.actions.act_window.view"].create(
            {
                "act_window_id": action.id,
                "view_id": timeline_view.id,
                "view_mode": "timeline",
            }
        )

    for index, mode in enumerate(_VIEW_ORDER):
        rows = action.view_ids.filtered(lambda v, m=mode: v.view_mode == m)
        if rows:
            rows.sequence = (index + 1) * 10


def post_init_hook(env):
    _ensure_timeline_view(env)
