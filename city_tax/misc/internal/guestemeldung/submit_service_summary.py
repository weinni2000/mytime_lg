#!/usr/bin/env python3
"""
Submit Meldezettel (Ortstaxe) registrations to Deskline for the bookings listed in a
Tiny Away "Service Summary" xlsx export, cross-referenced against the guest-details
Google Sheet (exported to data/guest_registration_sheet.csv) for the personal data
Deskline requires (salutation, nationality, date of birth, address) that the xlsx
itself does not contain.

Usage:
  python3 submit_service_summary.py --xlsx data/6_2026_....xlsx              # dry run, _logger.infos matches
  python3 submit_service_summary.py --xlsx data/6_2026_....xlsx --live       # actually submits to Deskline

Requires a valid Deskline session — run `deskline_login.py --auto-login` first.
"""

import argparse
import csv
import difflib
import logging
import os
import sys
from datetime import datetime

import openpyxl

_logger = logging.getLogger(__name__)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from deskline_login import submit_meldezettel  # noqa: E402

DEFAULT_SHEET_CSV = os.path.join(SCRIPT_DIR, "data", "guest_registration_sheet.csv")

SALUTATION_HERR = "9d1acf1a-db25-4578-8c42-a0658677a599"
SALUTATION_FRAU = "e87fa075-01b2-4bd5-9e77-5d0ba6e20a4b"
PERSON_GROUP_PFLICHTIG = ("98d0fd41-ae19-4e8d-a1a3-f5476069f967", "Pflichtig", "P")
PERSON_GROUP_FREI = ("63dddfc8-5953-4cbd-aae3-451c593bda02", "Frei", "F")

COUNTRY_MAP = {
    "deutschland": "DE",
    "germany": "DE",
    "german": "DE",
    "deutsch": "DE",
    "österreich": "AT",
    "osterreich": "AT",
    "austria": "AT",
    "austrian": "AT",
    "österreichisch": "AT",
    "steiermark": "AT",
    "schweiz": "CH",
    "switzerland": "CH",
    "czech republic": "CZ",
    "czech": "CZ",
    "česko": "CZ",
    "cz": "CZ",
    "česká republika": "CZ",
    "čr": "CZ",
    "české": "CZ",
    "štětí": "CZ",
    "polska": "PL",
    "poland": "PL",
    "holland": "NL",
    "netherlands": "NL",
    "israel": "IL",
    "ukraine": "UA",
    "dänemark": "DK",
    "denmark": "DK",
    "bosnien": "BA",
    "bosnia": "BA",
    "norwegen": "NO",
    "norway": "NO",
    "hungarian": "HU",
    "ungar": "HU",
    "hungary": "HU",
    "syrian": "SY",
    "syria": "SY",
    "hong kong": "HK",
}


def country_code(name):
    if not name:
        return None
    key = name.strip().lower()
    return COUNTRY_MAP.get(key)


def salutation_for(gender):
    return SALUTATION_HERR if (gender or "").strip().lower() == "male" else SALUTATION_FRAU


def parse_date(value, fmts):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    value = str(value).strip()
    if not value:
        return None
    for fmt in fmts:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def age_at(dob, on_date):
    if not dob or not on_date:
        return None
    return on_date.year - dob.year - ((on_date.month, on_date.day) < (dob.month, dob.day))


def iso(d):
    return f"{d.isoformat()}T00:00:00.000Z" if d else ""


def split_name(full_name):
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def load_bookings(xlsx_path):
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).strip() if h else "" for h in rows[0]]
    idx = {name: header.index(name) for name in header if name}

    bookings = []
    for row in rows[2:]:  # skip header + units row
        if not row or row[idx["Guest"]] is None:
            continue
        checkin = parse_date(row[idx["Check In"]], ["%d/%m/%Y"])
        checkout = parse_date(row[idx["Check Out"]], ["%d/%m/%Y"])
        bookings.append(
            {
                "confirmation_code": row[idx["Confirmation Code"]],
                "source": row[idx["Source"]],
                "guest_name": str(row[idx["Guest"]]).strip(),
                "guest_count": row[idx["# Guest"]],
                "checkin": checkin,
                "checkout": checkout,
                "email": row[idx["Email"]],
            }
        )
    return bookings


def load_sheet(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_match(booking, sheet_rows, max_day_diff=2, min_name_ratio=0.6):
    best, best_score = None, 0.0
    for row in sheet_rows:
        row_checkin = parse_date(row["checkin"], ["%m/%d/%Y"])
        if not row_checkin or not booking["checkin"]:
            continue
        day_diff = abs((row_checkin - booking["checkin"]).days)
        if day_diff > max_day_diff:
            continue
        ratio = difflib.SequenceMatcher(
            None, booking["guest_name"].lower(), row["full_name"].lower().strip()
        ).ratio()
        if ratio < min_name_ratio:
            continue
        score = ratio - day_diff * 0.05
        if score > best_score:
            best, best_score = row, score
    return best


def build_guest_payload(
    first,
    last,
    gender,
    country_name,
    street,
    dob,
    city,
    zip_code,
    arrival,
    planned_departure,
    departure,
    is_main,
    save_in_addresses,
):
    code = country_code(country_name) or "DE"
    dob_date = parse_date(dob, ["%m/%d/%Y"])
    age = age_at(dob_date, arrival) if dob_date else None
    pg_id, pg_name, pg_code = PERSON_GROUP_FREI if (age is not None and age < 16) else PERSON_GROUP_PFLICHTIG

    guest = {
        "firstName": first,
        "surname": last,
        "salutation": "Herr" if (gender or "").strip().lower() == "male" else "Frau",
        "salutationId": salutation_for(gender),
        "country": code,
        "nationality": code,
        "language": "de",
        "zip": zip_code or "",
        "city": city or "",
        "street": street or "",
        "personGroup": pg_id,
        "personGroupString": pg_name,
        "personGroupCode": pg_code,
        "arrival": iso(arrival),
        "plannedDeparture": iso(planned_departure),
        "departure": iso(departure),
        "saveInAddresses": save_in_addresses,
    }
    if dob_date:
        guest["dateOfBirth"] = iso(dob_date)
    if age is not None:
        guest["age"] = age
    if is_main:
        guest.update({"phone": "", "remark": ""})
    return guest


def main():
    parser = argparse.ArgumentParser(description="Submit Meldezettel from a Service Summary xlsx")
    parser.add_argument("--xlsx", required=True, help="Path to the Service Summary xlsx")
    parser.add_argument("--sheet-csv", default=DEFAULT_SHEET_CSV, help="Path to the guest-details CSV")
    parser.add_argument("--live", action="store_true", help="Actually submit to Deskline (default is dry-run)")
    args = parser.parse_args()

    bookings = load_bookings(args.xlsx)
    sheet_rows = load_sheet(args.sheet_csv)

    _logger.info(f"[→] {len(bookings)} bookings in {os.path.basename(args.xlsx)}\n")

    matched, unmatched = [], []
    for b in bookings:
        row = find_match(b, sheet_rows)
        if row:
            matched.append((b, row))
        else:
            unmatched.append(b)

    for b, row in matched:
        first, last = split_name(row["full_name"])
        main_guest = build_guest_payload(
            first,
            last,
            row["gender"],
            row["country"],
            row["street"],
            row["dob"],
            row["city"],
            row["zip"],
            b["checkin"],
            b["checkout"],
            b["checkout"],
            is_main=True,
            save_in_addresses=True,
        )

        additional_guests = []
        if row.get("guest2_name"):
            g2_first, g2_last = split_name(row["guest2_name"])
            additional_guests.append(
                build_guest_payload(
                    g2_first,
                    g2_last,
                    row.get("guest2_gender"),
                    row.get("guest2_nationality"),
                    row["street"],
                    None,
                    row["city"],
                    row["zip"],
                    b["checkin"],
                    b["checkout"],
                    b["checkout"],
                    is_main=False,
                    save_in_addresses=False,
                )
            )

        sheet_guest_count = 1 + (1 if row.get("guest2_name") else 0)
        if b["guest_count"] and b["guest_count"] > sheet_guest_count:
            _logger.info(
                f"[!] {b['guest_name']} ({b['checkin']}): booking has {b['guest_count']} guests, "
                f"sheet only has {sheet_guest_count} — {b['guest_count'] - sheet_guest_count} guest(s) "
                f"will be MISSING from this submission."
            )

        submit_meldezettel(main_guest, additional_guests, dry_run=not args.live)

    if unmatched:
        _logger.info(
            f"\n[!] {len(unmatched)} booking(s) had no match in the guest-details sheet — SKIPPED, not submitted:"
        )
        for b in unmatched:
            _logger.info(
                f"    - {b['guest_name']} ({b['source']}), check-in {b['checkin']}, "
                f"{b['guest_count']} guest(s), confirmation {b['confirmation_code']}"
            )
        _logger.info("    These need manual entry in Deskline or a Google Sheet entry to match against.")

    if not args.live:
        _logger.info("\n[i] Dry run — nothing was submitted. Re-run with --live to submit for real.")


if __name__ == "__main__":
    main()
