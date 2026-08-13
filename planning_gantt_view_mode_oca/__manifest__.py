{
    "name": "Planning Gantt View Mode OCA",
    "summary": "Add an OCA timeline view to the booking Planning schedule.",
    "version": "19.0.1.0.4",
    "category": "Human Resources/Planning",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        # "booking_engine",  # industry app
        "planning",
        "web_timeline",
    ],
    "data": [
        "views/planning_slot_views.xml",
    ],
    "assets": {
        "web.assets_backend_lazy": [
            "web_timeline/static/src/views/timeline/timeline_view.scss",
            "web_timeline/static/src/views/timeline/timeline_canvas.scss",
            "web_timeline/static/src/views/timeline/timeline_arch_parser.esm.js",
            "web_timeline/static/src/views/timeline/timeline_view.esm.js",
            "web_timeline/static/src/views/timeline/timeline_renderer.esm.js",
            "web_timeline/static/src/views/timeline/timeline_renderer.xml",
            "web_timeline/static/src/views/timeline/timeline_controller.esm.js",
            "web_timeline/static/src/views/timeline/timeline_controller.xml",
            "web_timeline/static/src/views/timeline/timeline_model.esm.js",
            "web_timeline/static/src/views/timeline/timeline_canvas.esm.js",
        ],
    },
    "installable": True,
    "application": False,
    "post_init_hook": "post_init_hook",
}
