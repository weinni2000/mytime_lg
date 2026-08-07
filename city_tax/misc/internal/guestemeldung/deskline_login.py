#!/usr/bin/env python3
# pylint: disable=print-used
"""
Deskline Identity Login Automation

Automates login to identity.deskline.net using Playwright,
saves session cookies/tokens for later use with webclient4.deskline.net.

Usage:
  python3 deskline_login.py                     # Interactive login (opens browser)
  python3 deskline_login.py --headless          # Headless login
  python3 deskline_login.py --credentials user:pass
                                                  # Auto-fill (less secure, not recommended
                                                  # for permanent storage)
  python3 deskline_login.py --load-cookies      # Test if saved session still works
  python3 deskline_login.py --auto-login        # Full automated login using .env credentials

Saves:
  - tmp/deskline_cookies.json  (Playwright cookies format)
  - tmp/deskline_session.json  (session tokens extracted from localStorage/cookies)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(SCRIPT_DIR, "tmp", "deskline_cookies.json")
SESSION_FILE = os.path.join(SCRIPT_DIR, "tmp", "deskline_session.json")

# Load .env from script directory
_env_file = Path(SCRIPT_DIR) / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            k, _, v = _line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

DESKLINE_USERNAME = os.environ.get("USERNAME", "")
DESKLINE_PASSWORD = os.environ.get("PASSWORD", os.environ.get("PW", ""))

# Deskline Identity base URL
IDENTITY_BASE = "https://identity.deskline.net"
WEBCLIENT_BASE = "https://webclient4.deskline.net"

# Deskline WebClient login URL (generates fresh OIDC parameters)
WEBCLIENT_LOGIN_URL = "https://webclient4.deskline.net/AT2/de/login"


def save_cookies(context):
    """Save cookies from browser context to file."""
    os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
    cookies = context.cookies()
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f, indent=2)
    print(f"[✓] Cookies saved: {COOKIES_FILE} ({len(cookies)} cookies)")
    return cookies


def save_session_tokens(page):
    """Extract and save tokens from localStorage and sessionStorage."""
    tokens = {}

    try:
        local_storage = page.evaluate("() => JSON.stringify(window.localStorage)")
        tokens["localStorage"] = json.loads(local_storage)
    except Exception as e:
        print(f"[!] Could not read localStorage: {e}")

    try:
        session_storage = page.evaluate("() => JSON.stringify(window.sessionStorage)")
        tokens["sessionStorage"] = json.loads(session_storage)
    except Exception as e:
        print(f"[!] Could not read sessionStorage: {e}")

    cookies = page.context.cookies()
    oidc_cookies = [c for c in cookies if "idsrv" in c["name"].lower() or "identity" in c["name"].lower()]
    if oidc_cookies:
        tokens["oidcCookies"] = oidc_cookies

    tokens["currentUrl"] = page.url
    tokens["savedAt"] = datetime.now(timezone.utc).isoformat()

    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"[✓] Session tokens saved: {SESSION_FILE}")


def load_cookies(context):
    """Load previously saved cookies into browser context."""
    if not os.path.exists(COOKIES_FILE):
        print("[!] No saved cookies found.")
        return False

    with open(COOKIES_FILE) as f:
        cookies = json.load(f)

    for cookie in cookies:
        if "name" in cookie and "value" in cookie and "domain" in cookie:
            try:
                context.add_cookies([cookie])
            except Exception as e:
                print(f"[!] Could not set cookie {cookie.get('name')}: {e}")

    print(f"[✓] Loaded {len(cookies)} cookies from {COOKIES_FILE}")
    return True


def check_session_valid(page):
    """Check if the current session is still valid by navigating to WebClient4."""
    page.goto(WEBCLIENT_BASE, wait_until="load", timeout=30000)
    time.sleep(2)

    current_url = page.url
    if "Account/Login" in current_url or "identity.deskline.net" in current_url:
        print("[✗] Session expired or invalid — redirected to login page.")
        return False
    else:
        print(f"[✓] Session valid! Reached: {current_url[:80]}")
        return True


def login_interactive(headless=False, credentials=None):
    """
    Log into Deskline WebClient via OIDC flow.
    Visits WebClient login URL first (generates fresh OIDC params),
    then completes login on identity.deskline.net.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--no-sandbox"] if headless else [],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="de-DE",
        )
        page = context.new_page()

        if headless:
            load_cookies(context)

        print(f"[→] Navigating to WebClient login: {WEBCLIENT_LOGIN_URL}")
        try:
            page.goto(WEBCLIENT_LOGIN_URL, wait_until="load", timeout=30000)
        except Exception as exc:
            print(f"[!] Navigation did not fully settle, continuing anyway: {exc}")
        time.sleep(2)

        current_url = page.url
        print(f"[→] Current URL: {current_url[:100]}")

        if "Account/Login" not in current_url:
            print("[✓] No login page — session might already be valid!")
            if "webclient4" in current_url and "login" not in current_url.lower():
                print("[✓] Already logged into WebClient4!")
                save_cookies(context)
                save_session_tokens(page)
                input("\nPress Enter to close browser...")
                browser.close()
                return

        if credentials:
            username, password = credentials.split(":", 1)
            print(f"[→] Auto-filling credentials for: {username}")

            page.wait_for_selector('input[name="Username"]', timeout=15000)
            page.fill('input[name="Username"]', username)
            page.fill('input[name="Password"]', password)

            print("[→] Submitting login form...")
            page.click('button.btn-primary, button[type="submit"], input[type="submit"]')

            time.sleep(5)
            try:
                page.wait_for_load_state("load", timeout=30000)
            except Exception as exc:
                print(f"[!] Page load did not fully settle, continuing anyway: {exc}")
            time.sleep(3)
        else:
            if headless:
                print("[!] Headless mode requires --credentials or --load-cookies")
                browser.close()
                return

            print("\n[!] Browser open — please log in manually.")
            print("[!] This script will detect the redirect and save the session.")
            print("[!] Waiting for login to complete (max 5 minutes)...\n")

            for _ in range(150):
                current_url = page.url
                if "Account/Login" not in current_url and "identity.deskline" not in current_url:
                    print(f"[→] Login detected! Redirected to: {current_url[:100]}")
                    time.sleep(3)
                    break
                time.sleep(2)
            else:
                print("[✗] Timeout waiting for login.")
                browser.close()
                return

        print("[→] Saving session data...")
        save_cookies(context)
        save_session_tokens(page)

        print(f"\n[✓] Login complete. Current URL: {page.url[:100]}")

        input("\nPress Enter to close browser and exit...")
        browser.close()


def test_session():
    """Test if saved session is still valid."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context()

        if not load_cookies(context):
            print("[!] No session to test.")
            browser.close()
            return

        page = context.new_page()

        if check_session_valid(page):
            cookies = context.cookies()
            print(f"\nActive cookies: {len(cookies)}")
            for c in cookies:
                if "idsrv" in c["name"].lower() or "session" in c["name"].lower() or "token" in c["name"].lower():
                    print(f"  {c['name']}: {c['value'][:30]}... (domain: {c['domain']})")

        browser.close()


def auto_login():
    """
    Full automated login using credentials from .env (USERNAME / PASSWORD).
    Uses Playwright to complete the full OIDC flow.
    """
    config_path = os.path.join(SCRIPT_DIR, "tmp", "deskline_credentials.json")
    if DESKLINE_USERNAME and DESKLINE_PASSWORD:
        config = {"username": DESKLINE_USERNAME, "password": DESKLINE_PASSWORD}
    elif os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
    else:
        print("[!] No credentials found. Set USERNAME/PASSWORD in .env or run --save-credentials.")
        return

    print(f"[→] Auto-login for: {config['username']}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="de-DE",
        )

        load_cookies(context)

        page = context.new_page()

        print("[→] Navigating to WebClient...")
        try:
            page.goto(WEBCLIENT_LOGIN_URL, wait_until="load", timeout=30000)
        except Exception as exc:
            print(f"[!] Navigation did not fully settle, continuing anyway: {exc}")
        time.sleep(2)

        current_url = page.url
        print(f"[→] Current URL: {current_url[:100]}")

        if "Account/Login" in current_url or "identity.deskline" in current_url:
            print("[→] Login required — filling credentials...")
            page.wait_for_selector('input[name="Username"]', timeout=15000)
            page.fill('input[name="Username"]', config["username"])
            page.fill('input[name="Password"]', config["password"])

            print("[→] Submitting...")
            page.click('button.btn-primary, button[type="submit"], input[type="submit"]')

            time.sleep(5)
            try:
                page.wait_for_load_state("load", timeout=30000)
            except Exception as exc:
                print(f"[!] Page load did not fully settle, continuing anyway: {exc}")
            time.sleep(3)

        final_url = page.url
        print(f"[→] Final URL: {final_url[:100]}")

        if "webclient4" in final_url and "login" not in final_url.lower():
            print("[✓] Login successful! WebClient loaded.")
            save_cookies(context)
            save_session_tokens(page)
        else:
            print("[✗] Login may have failed. Need to debug.")

        browser.close()


def submit_meldezettel(main_guest, additional_guests=None, dry_run=False):
    """
    Submit a guest registration (Meldezettel / visitor registration form) via the Deskline API.
    Uses saved session cookies. Requires a successful login first (see auto_login()).
    """
    import urllib.error
    import urllib.request

    additional_guests = additional_guests or []

    if not os.path.exists(COOKIES_FILE):
        print("[!] No saved cookies found. Run login first.")
        return

    def build_salutation_list():
        return [
            {"Value": "00000000-0000-0000-0000-000000000000", "Name": "Bitte wählen..."},
            {"Value": "9d1acf1a-db25-4578-8c42-a0658677a599", "Name": "Herr (Herrn)"},
            {"Value": "e87fa075-01b2-4bd5-9e77-5d0ba6e20a4b", "Name": "Frau (Frau)"},
            {"Value": "02549dc1-9b34-47ab-b9ad-8a8090d39a9e", "Name": "ohne Anrede (ohne Anrede)"},
        ]

    def build_person_groups():
        return [
            {"Value": "00000000-0000-0000-0000-000000000000", "Name": "Bitte wählen..."},
            {
                "Value": "98d0fd41-ae19-4e8d-a1a3-f5476069f967",
                "Name": "Pflichtig",
                "Type": 1,
                "AgeFrom": 16,
                "AgeTo": 100,
                "DisableInWebClient": False,
            },
            {
                "Value": "63dddfc8-5953-4cbd-aae3-451c593bda02",
                "Name": "Frei",
                "Type": 3,
                "AgeFrom": 0,
                "AgeTo": 15,
                "DisableInWebClient": False,
            },
        ]

    def build_guest(guest, is_main=True):
        g = {
            "Salutation": "",
            "SalutationId": guest.get(
                "salutationId",
                "9d1acf1a-db25-4578-8c42-a0658677a599"
                if guest.get("salutation") == "Herr"
                else "e87fa075-01b2-4bd5-9e77-5d0ba6e20a4b",
            ),
            "Salutations": build_salutation_list(),
            "CountryCode": guest.get("country", "DE"),
            "Nationality": guest.get("nationality", "DE"),
            "TravelDocumentType": None,
            "invalidDateOfBirth": False,
            "GuestLanguage": guest.get("language", "de"),
            "Phone": guest.get("phone", ""),
            "SaveInGuestAddresses": guest.get("saveInAddresses", True),
            "GuestDataProcessingAgreement": False,
            "HasDeparture": True,
            "PersonGroups": build_person_groups(),
            "PersonGroup": guest.get("personGroup", "98d0fd41-ae19-4e8d-a1a3-f5476069f967"),
            "PersonGroupString": guest.get("personGroupString", "Pflichtig"),
            "PersonGroupCode": guest.get("personGroupCode", "P"),
            "FirstName": guest["firstName"],
            "editMode": True,
            "Surname": guest["surname"],
            "ZipCode": guest.get("zip", ""),
            "City": guest.get("city", ""),
            "Street": guest.get("street", ""),
            "Remark": guest.get("remark", ""),
            "arrivalEqualToDeparture": False,
            "Arrival": guest.get("arrival", ""),
            "PlannedDeparture": guest.get("plannedDeparture", ""),
            "Departure": guest.get("departure", ""),
            "showEmailValidationMessage": False,
            "showPhoneValidationMessage": False,
        }

        if is_main:
            g.update(
                {
                    "ArrivalBy": "00000000-0000-0000-0000-000000000000",
                    "Motivation": "00000000-0000-0000-0000-000000000000",
                    "Recommendation": "00000000-0000-0000-0000-000000000000",
                    "GuestInterestIDs": [],
                    "MarketingInfo": False,
                }
            )

        if guest.get("dateOfBirth"):
            g["DateOfBirth"] = guest["dateOfBirth"]
        if guest.get("age"):
            g["Age"] = guest["age"]

        return g

    payload = {
        "MainGuest": build_guest(main_guest, is_main=True),
        "AdditionalGuests": [build_guest(ag, is_main=False) for ag in additional_guests],
        "MasterId": "00000000-0000-0000-0000-000000000000",
        "Summary": None,
    }
    full_payload = {"model": json.dumps(payload)}

    url = (
        "https://webclient4.deskline.net/AT2/de/visitorregistrationforms/"
        "savevtsheet/04b8e48f-64fd-420b-8bbb-7d0c25167aff"
        "?dbOv=MW9&headerType=0&subType=0"
    )

    arrival = main_guest.get("arrival", "?")[:10]
    departure = main_guest.get("departure", "?")[:10]
    print(
        f"[→] Meldezettel: {main_guest.get('firstName', '?')} {main_guest.get('surname', '?')} "
        f"(+{len(additional_guests)} additional), {arrival} → {departure}"
    )

    if dry_run:
        print("  [DRY RUN] not sent")
        return None

    with open(COOKIES_FILE) as f:
        cookies = json.load(f)
    cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://webclient4.deskline.net",
        "Referer": "https://webclient4.deskline.net/AT2/de/visitorregistrationforms/guestregistration/04b8e48f-64fd-420b-8bbb-7d0c25167aff?dbOv=MW9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookie_header,
    }
    body = json.dumps(full_payload).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_text = resp.read().decode("utf-8")
            print(f"  [✓] {resp.status}: {response_text[:200]}")
            return response_text
    except urllib.error.HTTPError as e:
        print(f"  [✗] HTTP {e.code}: {e.read().decode('utf-8')[:300]}")
    except Exception as e:
        print(f"  [✗] Error: {e}")
    return None


def export_curl_commands():
    """Generate cURL commands for API access using saved cookies."""
    if not os.path.exists(COOKIES_FILE):
        print("[!] No cookies file found. Run login first.")
        return

    with open(COOKIES_FILE) as f:
        cookies = json.load(f)

    cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    print("# Use these cookies with curl:\n")
    print(f"curl -b '{cookie_header}' {WEBCLIENT_BASE}\n")
    print("# Or save as cookie jar:\n")
    print(f"curl -b {COOKIES_FILE} -c {COOKIES_FILE} {WEBCLIENT_BASE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deskline Identity Login Automation")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (requires --credentials)")
    parser.add_argument("--credentials", help="Login credentials in format 'username:password'")
    parser.add_argument("--load-cookies", action="store_true", help="Test saved cookies")
    parser.add_argument("--export-curl", action="store_true", help="Export cURL commands from saved cookies")
    parser.add_argument("--auto-login", action="store_true", help="Full automated login using .env credentials")

    args = parser.parse_args()

    if args.export_curl:
        export_curl_commands()
    elif args.load_cookies:
        test_session()
    elif args.auto_login:
        auto_login()
    else:
        login_interactive(headless=args.headless, credentials=args.credentials)
