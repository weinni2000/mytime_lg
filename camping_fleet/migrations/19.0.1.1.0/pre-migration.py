LEGACY_CATEGORY_MAPPING = {
    "Hochdachkombi": "Camper Van",
    "PKW": "Car",
    "Wohnmobil": "Motorhome / RV",
    "Wohnwagen + PKW": "Caravan",
    "Dachzelt": "Tent (Car next to Tent)",
    "LKW": "Motorhome / RV",
    "Fahrrad": "Bicycle",
    "Sonstiges": "Motorhome / RV",
    "Motorrad": "Motorcycle",
}


def migrate(cr, version):
    cr.execute(
        """
        SELECT vehicle.id, category.name
          FROM camping_fleet_vehicle AS vehicle
          JOIN fleet_vehicle_model_category AS category
            ON category.id = vehicle.category_id
        """
    )
    legacy_categories = dict(cr.fetchall())

    cr.execute("SELECT id, name FROM camping_vehicle_type")
    vehicle_type_ids = {name: record_id for record_id, name in cr.fetchall()}

    missing_types = {
        LEGACY_CATEGORY_MAPPING[name]
        for name in legacy_categories.values()
        if name in LEGACY_CATEGORY_MAPPING and LEGACY_CATEGORY_MAPPING[name] not in vehicle_type_ids
    }
    if missing_types:
        raise RuntimeError(
            "Cannot migrate camping vehicle categories; missing vehicle types: " + ", ".join(sorted(missing_types))
        )

    for vehicle_id, legacy_name in legacy_categories.items():
        target_name = LEGACY_CATEGORY_MAPPING.get(legacy_name)
        if not target_name:
            raise RuntimeError(f"Cannot migrate unknown camping vehicle category: {legacy_name}")
        cr.execute(
            "UPDATE camping_fleet_vehicle SET category_id = %s WHERE id = %s",
            (vehicle_type_ids[target_name], vehicle_id),
        )
