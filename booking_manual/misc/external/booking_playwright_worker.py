#!/usr/bin/env python3
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import psycopg2
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def exit_on_signal(signum, _frame):
    """Turn service stop signals into normal unwinding so VNC is cleaned up."""
    raise SystemExit(128 + signum)


def database_connection(request):
    parameters = {"dbname": request["database"]}
    for source, target in (
        ("db_host", "host"),
        ("db_port", "port"),
        ("db_user", "user"),
        ("db_password", "password"),
    ):
        if request.get(source):
            parameters[target] = request[source]
    return psycopg2.connect(**parameters)


def update_account(request, **values):
    allowed = {"login_state", "login_error", "session_cookies", "last_login", "worker_pid"}
    values = {key: value for key, value in values.items() if key in allowed}
    if not values:
        return
    assignments = ", ".join(f"{key} = %s" for key in values)
    with database_connection(request) as connection, connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE booking_account SET {assignments}, write_date = NOW() WHERE id = %s",
            [*values.values(), request["account_id"]],
        )


def wait_for_sms_code(request, timeout=600):
    update_account(request, login_state="waiting_sms")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with database_connection(request) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT temp_booking_key
                  FROM booking_account
                 WHERE id > %s AND temp_booking_key IS NOT NULL
                 ORDER BY id DESC LIMIT 1
                """,
                [request["baseline_id"]],
            )
            row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        time.sleep(2)
    raise TimeoutError("Timed out after 10 minutes waiting for the Booking.com SMS code.")


def first_visible(page, selectors, timeout=15000):
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                if locator.is_visible(timeout=500):
                    return locator
            except PlaywrightTimeoutError:
                continue
        page.wait_for_timeout(250)
    return None


def human_verification_visible(page):
    try:
        text = page.locator("body").inner_text(timeout=3000).lower()
    except PlaywrightTimeoutError:
        return False
    return "make sure you're human" in text or "captcha" in text


def complete_login_flow(page, request, timeout=600):  # noqa: C901
    """Continue from any page left by the manual challenge.

    Booking.com may return to the username page, reveal the password page, jump
    directly to SMS verification, or finish authentication. Re-evaluate the
    page continuously so manual actions in noVNC and automated actions can be
    mixed safely.
    """
    update_account(request, login_state="waiting_human")
    deadline = time.monotonic() + timeout
    password_submitted = False
    sms_submitted = False
    sms_method_selected = False
    sms_send_clicked = False
    while time.monotonic() < deadline:
        if "account.booking.com/sign-in" not in page.url:
            return

        password_page = "/sign-in/password" in page.url
        if not password_page:
            # Booking can request the password again after SMS verification.
            # Re-arm password submission once the first password page was left.
            password_submitted = False
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[autocomplete="current-password"]',
            'input[aria-label*="password" i]',
        ]
        if password_page:
            # Booking currently renders the password control as a text-like
            # input on some challenges, despite displaying an eye toggle.
            password_selectors.append('input:not([type="hidden"])')
        password = first_visible(page, password_selectors, timeout=1000)
        if password and not password_submitted:
            update_account(request, login_state="logging_in")
            password.fill(request["password"])
            submit = first_visible(page, ['button[type="submit"]'], timeout=3000)
            if not submit:
                raise RuntimeError("Booking.com Sign in button was not found.")
            submit.click()
            password_submitted = True
            page.wait_for_timeout(1500)
            continue

        code_input = None
        if not password_page:
            code_input = first_visible(
                page,
                [
                    'input[autocomplete="one-time-code"]',
                    'input[name*="code" i][inputmode="numeric"]',
                    'input[inputmode="numeric"]',
                ],
                timeout=1000,
            )
        if code_input and not sms_submitted:
            code_input.fill(wait_for_sms_code(request))
            verify = first_visible(page, ['button[type="submit"]'], timeout=3000)
            if not verify:
                raise RuntimeError("Booking.com verification button was not found.")
            verify.click()
            sms_submitted = True
            page.wait_for_timeout(1500)
            continue

        if not sms_send_clicked:
            send_sms = first_visible(
                page,
                [
                    'button:has-text("Send verification code")',
                    'button:has-text("Send code")',
                ],
                timeout=1000,
            )
            if send_sms:
                send_sms.click()
                sms_send_clicked = True
                page.wait_for_timeout(1500)
                continue

        if not sms_method_selected:
            sms_method = first_visible(
                page,
                [
                    'text="Text message (SMS)"',
                    "text=/Text message.*SMS/i",
                    "text=/SMS/i",
                ],
                timeout=1000,
            )
            if sms_method:
                sms_method.click()
                sms_method_selected = True
                page.wait_for_timeout(1500)
                continue

        username_selectors = [
            'input[name="loginname"]',
            'input[name="username"]',
            'input[autocomplete="username"]',
            'input[type="email"]',
            'input[aria-label*="username" i]',
        ]
        if "/sign-in?" in page.url:
            # The Partner/Extranet login shown after SMS uses a generic input
            # without the attributes of the first account-login page.
            username_selectors.append('form input:not([type="hidden"])')
        username = first_visible(page, username_selectors, timeout=1000)
        if username and not human_verification_visible(page):
            username.fill(request["username"])
            submit = first_visible(page, ['button[type="submit"]'], timeout=3000)
            if submit:
                # A username page always leads to a new password step, even if
                # another password was already submitted earlier in the flow.
                password_submitted = False
                submit.click()
                page.wait_for_timeout(1500)
                continue

        page.wait_for_timeout(500)
    raise TimeoutError("Timed out after 10 minutes waiting for Booking.com login completion.")


def start_interactive_display(request):
    runtime_dir = tempfile.mkdtemp(prefix="booking-manual-")
    display_number = 90
    display = f":{display_number}"
    vnc_port = 5901
    websocket_port = 6080
    password_file = os.path.join(runtime_dir, "vnc-password")
    x11vnc_log_path = f"/tmp/booking-manual-{request['account_id']}-x11vnc.log"
    websockify_log_path = f"/tmp/booking-manual-{request['account_id']}-websockify.log"
    with open(password_file, "w", encoding="utf-8") as password_handle:
        password_handle.write(request["vnc_password"] + "\n")
    os.chmod(password_file, 0o600)

    processes = []
    try:
        processes.append(
            subprocess.Popen(
                ["Xvfb", display, "-screen", "0", "1280x900x24", "-nolisten", "tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        time.sleep(1)
        x11vnc_log = open(x11vnc_log_path, "w", encoding="utf-8")
        websockify_log = open(websockify_log_path, "w", encoding="utf-8")
        processes.append(
            subprocess.Popen(
                [
                    "x11vnc",
                    "-display",
                    display,
                    "-rfbport",
                    str(vnc_port),
                    "-localhost",
                    "-forever",
                    "-shared",
                    "-passwdfile",
                    password_file,
                    "-noxdamage",
                    "-noxrecord",
                    "-noxfixes",
                ],
                stdout=x11vnc_log,
                stderr=subprocess.STDOUT,
            )
        )
        processes.append(
            subprocess.Popen(
                [
                    "websockify",
                    "--web",
                    "/usr/share/novnc",
                    f"127.0.0.1:{websocket_port}",
                    f"127.0.0.1:{vnc_port}",
                ],
                stdout=websockify_log,
                stderr=subprocess.STDOUT,
            )
        )
        time.sleep(1)
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("Could not start the interactive browser display.")
        yield display
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for log_handle in (locals().get("x11vnc_log"), locals().get("websockify_log")):
            if log_handle:
                log_handle.close()
        shutil.rmtree(runtime_dir, ignore_errors=True)


def perform_login(request):
    display_generator = start_interactive_display(request)
    display = next(display_generator)
    try:
        os.environ["DISPLAY"] = display
        os.makedirs(request["profile_dir"], mode=0o700, exist_ok=True)
        os.chmod(request["profile_dir"], 0o700)
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                request["profile_dir"],
                headless=False,
                args=["--no-sandbox"],
                locale="de-DE",
                viewport={"width": 1280, "height": 900},
            )
            try:
                if request.get("session_cookies"):
                    context.add_cookies(json.loads(request["session_cookies"]))
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(request["login_url"], wait_until="domcontentloaded", timeout=60000)

                if "account.booking.com/sign-in" in page.url:
                    username = first_visible(
                        page,
                        [
                            'input[name="loginname"]',
                            'input[autocomplete="username"]',
                            'input[type="email"]',
                            'input[name="username"]',
                        ],
                    )
                    if not username:
                        raise RuntimeError("Booking.com username field was not found.")
                    username.fill(request["username"])
                    button = first_visible(page, ['button[type="submit"]'])
                    if not button:
                        raise RuntimeError("Booking.com Continue button was not found.")
                    button.click()
                    page.wait_for_timeout(2000)
                    complete_login_flow(page, request)

                update_account(
                    request,
                    login_state="connected",
                    login_error=None,
                    session_cookies=json.dumps(context.cookies()),
                    last_login=time.strftime("%Y-%m-%d %H:%M:%S"),
                    worker_pid=None,
                )
            finally:
                context.close()
    finally:
        try:
            next(display_generator)
        except StopIteration:
            return


def main():
    signal.signal(signal.SIGTERM, exit_on_signal)
    signal.signal(signal.SIGINT, exit_on_signal)
    request = json.loads(sys.stdin.read())
    try:
        perform_login(request)
    except Exception as exc:  # noqa: BLE001 - persist failures for the Odoo user
        update_account(request, login_state="error", login_error=str(exc)[-2000:], worker_pid=None)
        raise


if __name__ == "__main__":
    main()
