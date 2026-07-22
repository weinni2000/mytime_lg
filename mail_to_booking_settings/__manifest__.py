{
    "name": "Mail to Booking Settings",
    "summary": "Local DeepSeek API key for the Mail to Booking module.",
    "version": "19.0.1.0.0",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "mail_to_booking",
    ],
    "data": [
        "data/fetchmail_server_data.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
