{
    "name": "Booking Engine Kanban Weekday",
    "summary": "Show the weekday in daily booking kanban group headers.",
    "version": "19.0.1.0.0",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "booking_engine",
        "web",
    ],
    "data": [
        "views/sale_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "booking_engine_kanban_weekday/static/src/js/booking_kanban_weekday.js",
            "booking_engine_kanban_weekday/static/src/xml/booking_kanban_weekday.xml",
        ],
    },
    "installable": True,
    "application": False,
}
