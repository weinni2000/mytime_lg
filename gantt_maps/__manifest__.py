{
    "name": "Gantt Maps",
    "version": "19.0.1.0.0",
    "author": "mytime.click",
    "category": "Hidden",
    "license": "OEEL-1",
    "depends": ["booking_engine", "camping_map_booking", "ressource_map", "web_gantt"],
    "data": ["views/planning_slot_views.xml"],
    "assets": {
        "web.assets_backend_lazy": [
            "gantt_maps/static/src/views/gantt_maps_view.js",
            "gantt_maps/static/src/views/gantt_maps_renderer.xml",
            "gantt_maps/static/src/views/gantt_maps.scss",
        ],
    },
    "installable": True,
}
