#!/usr/bin/env python3
# pylint: disable=print-used
"""
Standalone Playwright worker for the city_tax module's "Log in to Deskline" button.

Runs in its own OS process (invoked via subprocess from models/res_company.py) because
launching Playwright's browser directly inside an Odoo worker thread was observed to
crash with TargetClosedError / SIGTRAP -- likely Odoo's worker signal handling or
threading state interfering with Playwright's internal driver thread. A plain,
unrelated interactive shell in the same venv launches the same browser fine, so the
conflict is specific to running inside the Odoo process, not a missing dependency.

Reads a JSON request on stdin: {"username": ..., "password": ..., "region": ...}
Writes a JSON result to stdout: {"cookies": [...], "property_id": ..., "db_ov": ...}
or {"error": "..."} on failure.
"""

import json
import re
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_URL = "https://webclient4.deskline.net"
GUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
DB_OV_RE = re.compile(r"[?&]dbOv=([A-Za-z0-9]+)")


def discover_property(page):
    """Best-effort: the logged-in overview page has a direct <a href> to
    .../visitorregistrationforms/guestregistration/<property_id>?dbOv=<db_ov> in its
    navigation menu -- scan for it rather than guessing a property-less URL (which
    just renders an error page, no redirect)."""
    try:
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    except Exception:  # noqa: BLE001 - best-effort discovery, never fail the login over it
        return None, None
    for href in hrefs:
        if "visitorregistrationforms/guestregistration/" not in href:
            continue
        guid_match = GUID_RE.search(href)
        db_ov_match = DB_OV_RE.search(href)
        if guid_match and db_ov_match:
            return guid_match.group(0), db_ov_match.group(1)
    return None, None


def main():
    request = json.loads(sys.stdin.read())
    username = request["username"]
    password = request["password"]
    region = request["region"]

    login_url = f"{BASE_URL}/{region}/de/login"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 800}, locale="de-DE")
            page = context.new_page()
            try:
                page.goto(login_url, wait_until="load", timeout=30000)
            except PlaywrightTimeoutError:
                print(f"[worker] Timed out waiting for {login_url} to fully load, continuing anyway.")
            page.wait_for_timeout(2000)

            if "Account/Login" in page.url or "identity.deskline" in page.url:
                page.wait_for_selector('input[name="Username"]', timeout=15000)
                page.fill('input[name="Username"]', username)
                page.fill('input[name="Password"]', password)
                page.click('button.btn-primary, button[type="submit"], input[type="submit"]')
                try:
                    page.wait_for_load_state("load", timeout=30000)
                except PlaywrightTimeoutError:
                    print("[worker] Timed out waiting for post-login page load, continuing anyway.")
                page.wait_for_timeout(3000)

            final_url = page.url
            if "webclient4" not in final_url or "login" in final_url.lower():
                print(json.dumps({"error": f"Deskline login failed — still on the login page ({final_url})."}))
                return

            cookies = context.cookies()
            property_id, db_ov = discover_property(page)
        finally:
            browser.close()

    print(json.dumps({"cookies": cookies, "property_id": property_id, "db_ov": db_ov}))


if __name__ == "__main__":
    main()
