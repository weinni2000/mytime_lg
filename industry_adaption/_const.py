"""Selection rows of industry_real_estate whose XML IDs can go missing.

Each entry is ``(xmlid, field xmlid, value)``.  The rows are re-linked to
their XML ID before industry_real_estate is upgraded; without the link an
upgrade treats the existing rows as new records and hits the unique
constraint on ``(field_id, value)``.
"""

SELECTION_XMLIDS = (
    ("field_property_type_selection_apartment", "field_property_type", "Appartment"),
    ("field_property_type_selection_house", "field_property_type", "House"),
    ("field_property_type_selection_studio", "field_property_type", "Studio"),
    ("field_property_type_selection_office", "field_property_type", "Office"),
    (
        "field_property_type_selection_commercial_space",
        "field_property_type",
        "Commercial space",
    ),
    ("field_property_type_selection_warehouse", "field_property_type", "Warehouse"),
    ("field_property_type_selection_land", "field_property_type", "Land"),
    ("field_property_type_selection_garage", "field_property_type", "Garage"),
    ("field_property_type_selection_room", "field_property_type", "Room"),
    (
        "field_property_invoice_status_selection_no",
        "field_property_invoice_status",
        "no",
    ),
    (
        "field_property_invoice_status_selection_invoiced",
        "field_property_invoice_status",
        "invoiced",
    ),
    (
        "field_property_invoice_status_selection_to_invoice",
        "field_property_invoice_status",
        "to_invoice",
    ),
)
