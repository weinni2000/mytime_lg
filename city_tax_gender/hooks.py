_CALCULATED_GENDER_PROPERTY = {
    "name": "calculated_gender",
    "string": "Calculated Gender",
    "type": "selection",
    "selection": [["male", "Male"], ["female", "Female"]],
    "ai": True,
    "system_prompt": (
        "<p>Deduce the gender of the guest from their full name "
        '<span data-ai-field="name">Name</span>. Return "Male" or "Female". '
        "If the gender cannot be reliably determined from the name, leave the value empty.</p>"
    ),
}


def _get_partner_properties_definition(env):
    return env["properties.base.definition"].sudo()._get_definition_for_property_field("res.partner", "properties")


def post_init_hook(env):
    definition_record = _get_partner_properties_definition(env)
    properties_definition = definition_record.properties_definition or []
    if not any(prop.get("name") == _CALCULATED_GENDER_PROPERTY["name"] for prop in properties_definition):
        definition_record.write({"properties_definition": properties_definition + [_CALCULATED_GENDER_PROPERTY]})


def uninstall_hook(env):
    definition_record = _get_partner_properties_definition(env)
    properties_definition = definition_record.properties_definition or []
    definition_record.write(
        {
            "properties_definition": [
                prop for prop in properties_definition if prop.get("name") != _CALCULATED_GENDER_PROPERTY["name"]
            ]
        }
    )
