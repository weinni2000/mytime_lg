from odoo.exceptions import UserError

from ._const import (
    _DESKLINE_PERSON_GROUP_AGE_THRESHOLD,
    _DESKLINE_PERSON_GROUP_FREI,
    _DESKLINE_PERSON_GROUP_PFLICHTIG,
    _DESKLINE_PERSON_GROUPS,
    _DESKLINE_SALUTATION_UNSET,
    _DESKLINE_SALUTATIONS,
)

# Fields Deskline's API rejects as "Daten ungültig" when blank, mapped to their
# human labels for the pre-flight validation error.
_REQUIRED_PAYLOAD_FIELDS = {
    "CountryCode": "Country/Nationality",
    "Arrival": "Arrival",
    "PlannedDeparture": "Planned Departure",
    "Departure": "Departure",
}


def split_name(full_name):
    parts = (full_name or "").split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def iso_date(value):
    return f"{value.isoformat()}T00:00:00.000Z" if value else ""


def build_guest_payload(guest_line):
    """Build a single Deskline guest payload. `guest_line` can be an x_guests_line
    or y_guests_line record — both expose the same x_guest_* field names."""
    first_name, surname = split_name(guest_line.x_guest_name)
    country = guest_line.x_calc_nationality_id or guest_line.x_guest_country_id
    person_group_id, person_group_name, person_group_code = (
        _DESKLINE_PERSON_GROUP_FREI
        if guest_line.x_guest_age and guest_line.x_guest_age < _DESKLINE_PERSON_GROUP_AGE_THRESHOLD
        else _DESKLINE_PERSON_GROUP_PFLICHTIG
    )

    guest = {
        "Salutation": "",
        "SalutationId": guest_line.x_anrede or _DESKLINE_SALUTATION_UNSET,
        "Salutations": _DESKLINE_SALUTATIONS,
        "CountryCode": country.code or "",
        "Nationality": country.code or "",
        "TravelDocumentType": None,
        "invalidDateOfBirth": False,
        "GuestLanguage": (guest_line.x_guest_lang or "de")[:2],
        "Phone": "",
        "SaveInGuestAddresses": guest_line.x_save_as_contact,
        "GuestDataProcessingAgreement": False,
        # HasDeparture=False (the web form's own default for a fresh registration)
        # files this as a "Voranmeldung" draft that never gets transmitted to the
        # municipality until manually converted on arrival day. HasDeparture=True
        # + a real Departure date, combined with headerType=7 in
        # res_company._submit_deskline_payload(), is what's confirmed (via a real
        # captured request/response) to produce an actual numbered Meldeschein
        # straight away instead.
        #
        # Important limitation, confirmed by bisection against the live API: Deskline
        # rejects ("Daten ungültig") ANY submission whose Arrival date is in the past
        # relative to today, regardless of every other field -- this matches the web
        # UI's own text that a Voranmeldung "must be converted into a report on the
        # arrival day". There is currently no known way to submit a Meldeschein for a
        # stay that has already happened through this endpoint.
        "HasDeparture": True,
        "PersonGroups": _DESKLINE_PERSON_GROUPS,
        "PersonGroup": person_group_id,
        "PersonGroupString": person_group_name,
        "PersonGroupCode": person_group_code,
        "FirstName": first_name,
        "editMode": True,
        "Surname": surname,
        "ZipCode": guest_line.x_guest_zip or "",
        "City": guest_line.x_guest_city or "",
        "Street": guest_line.x_guest_street or "",
        "Remark": "",
        "arrivalEqualToDeparture": False,
        "Arrival": iso_date(guest_line.x_arrival_date),
        "PlannedDeparture": iso_date(guest_line.x_planned_departure_date or guest_line.x_departure_date),
        "Departure": iso_date(guest_line.x_departure_date),
        "showEmailValidationMessage": False,
        "showPhoneValidationMessage": False,
    }
    if guest_line.x_main_guest:
        guest.update(
            {
                "ArrivalBy": _DESKLINE_SALUTATION_UNSET,
                "Motivation": _DESKLINE_SALUTATION_UNSET,
                "Recommendation": _DESKLINE_SALUTATION_UNSET,
                "GuestInterestIDs": [],
                "MarketingInfo": False,
            }
        )
    if guest_line.x_guest_birthdate:
        guest["DateOfBirth"] = iso_date(guest_line.x_guest_birthdate)
    if guest_line.x_guest_age:
        guest["Age"] = guest_line.x_guest_age

    missing = [label for key, label in _REQUIRED_PAYLOAD_FIELDS.items() if not guest[key]]
    if missing:
        raise UserError(
            guest_line.env._(
                "Guest %(name)s is missing required field(s) for Deskline: %(fields)s",
                name=guest_line.x_guest_name or guest_line.display_name,
                fields=", ".join(missing),
            )
        )
    return guest


def build_submission_payload(guest_lines, master_id=_DESKLINE_SALUTATION_UNSET):
    """Build the full MainGuest/AdditionalGuests payload for a set of guest lines.
    `master_id` is the zero GUID for a new registration, or an existing registration's
    masterId (from a prior submission's response) to update/convert that same one."""
    main_line = guest_lines.filtered("x_main_guest")[:1] or guest_lines[:1]
    additional_lines = guest_lines - main_line
    return {
        "MainGuest": build_guest_payload(main_line),
        "AdditionalGuests": [build_guest_payload(guest_line) for guest_line in additional_lines],
        "MasterId": master_id,
        "Summary": None,
    }
