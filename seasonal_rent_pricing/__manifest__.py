{
    "name": "Seasonal Rent Pricing",
    "summary": "Apply pricelist discount rules to rental days that fall inside " "the rule's date window.",
    "version": "19.0.1.0.0",
    "category": "Sales/Rental",
    "license": "OPL-1",
    "author": "mytime.click",
    "website": "https://mytime.click",
    "depends": [
        "sale_renting",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_pricelist_item_views.xml",
        "views/product_pricelist_views.xml",
        "views/product_template_views.xml",
        "views/seasonal_rent_price_calendar_views.xml",
    ],
    "installable": True,
}
