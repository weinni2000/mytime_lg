{
    "name": "Camping Communication",
    "summary": "Send product-specific camping confirmation emails from sale orders.",
    "version": "19.0.1.0.2",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "mail",
        "sale",
    ],
    "data": [
        "data/mail_template_data.xml",
        "views/product_template_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
