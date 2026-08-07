# Salutation codes as used by Deskline's guest-registration API: the stored
# value IS the Deskline SalutationId GUID (from a real captured savevtsheet
# request, misc/internal/requests/test.json), not an arbitrary local code.
_X_ANREDE_SELECTION = [
    ("00000000-0000-0000-0000-000000000000", "Bitte wählen..."),
    ("9d1acf1a-db25-4578-8c42-a0658677a599", "Herr (Herrn)"),
    ("e87fa075-01b2-4bd5-9e77-5d0ba6e20a4b", "Frau (Frau)"),
    ("5b1528d2-fd4e-4a71-9955-d8dce8b890fd", "Damen und Herren ()"),
    ("bb8c2827-c101-4da5-aadf-ea4a82948ab0", "Familie (Familie)"),
    ("079bf6d5-ab63-46a7-825d-622d55734c62", "Herr und Frau (Herr und Frau)"),
    ("848202d4-73ae-46c8-971a-10155ccacc2e", "Diverse (Diverse)"),
    ("7b24abe1-b47f-499e-b787-7718de10d300", "Inter (Inter)"),
    ("1842de95-2af9-4503-a4b9-7f23e27a9e6f", "Offen (Offen)"),
    ("84cd0088-e889-470c-a164-5856655ed625", "Keine Angabe (Keine Angabe)"),
    ("9ad626ef-1c63-42c1-b769-3bd66588be6b", "Herr mit Namen (Herr)"),
    ("d05b9943-5b7a-42ea-b848-88a1dbfd80b0", "Frau mit Namen (Frau)"),
    ("220eae5c-764e-4ae7-ae9f-0f4906160d92", " (An)"),
    ("17ebc4f7-908c-4f17-a56f-d28095f8cc30", " (Familie)"),
    ("dc5bb920-f649-4ad9-91b2-8456af076789", " (Herr und Frau)"),
    ("918ed87e-05fd-46e5-9ce7-a93de4be4378", " (Firma)"),
    ("4b48a876-b28d-469d-b9ed-d74ea6a555f6", "Herr Dr. mit Namen (Herr Dr.)"),
    ("c1df69cd-536b-4deb-b927-d60a64b7edba", "Frau Dr. mit Namen (Frau Dr.)"),
    ("01b6e7ae-164c-4bdd-8ad0-5b6ae6fbf368", "Herr Ing. mit Namen (Herr Ing.)"),
    ("24ebe640-548d-4c2c-bce8-5dc1aa38ece4", "Frau Ing. mit Namen (Frau Ing.)"),
    ("ff9c0fb3-fcec-46c0-a004-d5dbf61baeac", "Herr Mag. mit Namen (Herr Mag.)"),
    ("f492b45d-9f65-4934-a5ee-872db6352d26", "Frau Mag. mit Namen (Frau Mag.)"),
    ("3fd25d69-dcaf-436e-82fc-55a5468482a0", "Herr DI mit Namen (Herr DI)"),
    ("0426e486-ce77-434e-8d39-fe67fa59156c", "Frau DI mit Namen (Frau DI)"),
    ("61e46b98-f6d9-4000-a626-912f7b33976b", "Herr Dipl.-Kfm. mit Namen (Herr Dipl.-Kfm.)"),
    ("6276082d-6ef7-4dab-af81-6158f346b2dd", "Frau Dipl.-Kffr. mit Namen (Frau Dipl.-Kffr.)"),
    ("5375d3ba-b5ee-4cea-b689-1f97a3845882", "Herr Dipl.-Betriebswirt (Herr Dipl.-Betriebswirt)"),
    ("f7cb9ea3-4162-40c2-976e-8c61abc02997", "Frau Dipl.-Betriebswirtin (Frau Dipl.-Betriebswirtin)"),
    ("8981d674-d9c9-4dda-843d-f08032396db3", "Herr Prof. mit Namen (Herr Prof.)"),
    ("beb92c5b-2df1-4b0f-8c10-7bfaa9a6d1d6", "Frau Prof. mit Namen (Frau Prof.)"),
    ("02549dc1-9b34-47ab-b9ad-8a8090d39a9e", "ohne Anrede (ohne Anrede)"),
    ("43853f54-8eb1-427d-a513-aaedfd33182e", " (Reisebüro)"),
]

# Handy names for the entries above that are referenced individually elsewhere
# (default value, gender-based defaulting, the "unset" fallback for payloads).
_DESKLINE_SALUTATION_UNSET = _X_ANREDE_SELECTION[0][0]
_DESKLINE_SALUTATION_HERR = _X_ANREDE_SELECTION[1][0]
_DESKLINE_SALUTATION_FRAU = _X_ANREDE_SELECTION[2][0]
_DESKLINE_SALUTATION_DAMEN_UND_HERREN = _X_ANREDE_SELECTION[3][0]
_DESKLINE_SALUTATION_OHNE = _X_ANREDE_SELECTION[30][0]

# Guest-registration completeness: "light" applies to accompanying guests,
# "full" applies to the main guest of a stay (see x_guests_line.x_main_guest).
_GUEST_LIGHT_REQUIRED_FIELDS = ["name", "x_anrede", "x_nationality"]
_GUEST_FULL_REQUIRED_FIELDS = [
    "name",
    "x_anrede",
    "title_id",
    "lang",
    "country_id",
    "x_nationality",
    "zip",
    "city",
    "street",
]
_GUEST_FIELD_LABELS = {
    "name": "Name",
    "x_anrede": "Anrede",
    "title_id": "Title",
    "lang": "Language",
    "country_id": "Country",
    "x_nationality": "Nationality",
    "zip": "Zip",
    "city": "City",
    "street": "Street",
}

_DESKLINE_PERSON_GROUP_PFLICHTIG = ("98d0fd41-ae19-4e8d-a1a3-f5476069f967", "Pflichtig", "P")
_DESKLINE_PERSON_GROUP_FREI = ("63dddfc8-5953-4cbd-aae3-451c593bda02", "Frei", "F")
_DESKLINE_PERSON_GROUP_AGE_THRESHOLD = 16

# The Deskline web form always submits the full salutation/person-group reference
# lists alongside a guest, regardless of the guest's own values (from
# deskline_login.py's build_salutation_list()/build_person_groups()). Derived
# from _X_ANREDE_SELECTION itself now that both use the same real GUIDs.
_DESKLINE_SALUTATIONS = [{"Value": value, "Name": name} for value, name in _X_ANREDE_SELECTION]
_DESKLINE_PERSON_GROUPS = [
    {"Value": _DESKLINE_SALUTATION_UNSET, "Name": "Bitte wählen..."},
    {
        "Value": _DESKLINE_PERSON_GROUP_PFLICHTIG[0],
        "Name": "Pflichtig",
        "Type": 1,
        "AgeFrom": 16,
        "AgeTo": 100,
        "DisableInWebClient": False,
    },
    {
        "Value": _DESKLINE_PERSON_GROUP_FREI[0],
        "Name": "Frei",
        "Type": 3,
        "AgeFrom": 0,
        "AgeTo": 15,
        "DisableInWebClient": False,
    },
]
