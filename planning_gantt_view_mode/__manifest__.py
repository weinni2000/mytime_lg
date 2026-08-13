{
    "name": "Planning Gantt View Mode",
    "summary": "Toggle the Planning schedule between planning mode (all bookable"
    " resources) and watching mode (only booked rows).",
    "version": "19.0.1.0.1",
    "category": "Human Resources/Planning",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "planning",
    ],
    "assets": {
        # The Planning gantt view (PlanningGanttModel/Controller and its
        # templates) is shipped in the lazy backend bundle, so our patch and
        # template inheritance must live in the same bundle to resolve the
        # `@planning/views/planning_gantt/**` imports.
        "web.assets_backend_lazy": [
            "planning_gantt_view_mode/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
