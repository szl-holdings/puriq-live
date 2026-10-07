"""Browser trust-boundary regression with explicitly synthetic server results."""
import json
import os
import time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, expect


def fixture(age_limit=30):
    now = time.time()
    return {
        "status": "REVIEW", "truth_label": "REPORTED", "symbol": "BTC",
        "price_text": "100.25", "trading_enabled": False,
        "verification": {"core_valid": True, "record_valid": True,
                         "verification_scope": "full-record", "fresh": True},
        "provider_print": {"at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
                           "sources": 5, "note": "SYNTHETIC_BROWSER_FIXTURE"},
        "receipt": {"observed_at": now, "policy": {"max_age_seconds": age_limit},
                    "receipt_id": "synthetic"}, "decision_reasons": [],
    }


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(os.environ.get("PURIQ_BROWSER_BASE", "http://127.0.0.1:7860") + "/signed-prices")

    def load(data, delay=0):
        page.unroute("**/api/puriq/v1/signed-price?*")
        def respond(route):
            if delay:
                time.sleep(delay)
            route.fulfill(status=200, content_type="application/json", body=json.dumps(data))
        page.route("**/api/puriq/v1/signed-price?*", respond)
        page.locator("#refresh").click()
        expect(page.locator("#refresh")).to_be_enabled()

    load(fixture())
    expect(page.locator("#price")).to_have_text("100.25")
    assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
    invalid = fixture()
    invalid["verification"]["record_valid"] = False
    invalid["provider_print"]["note"] = "<img src=x onerror=alert(1)>"
    load(invalid)
    expect(page.locator("#price")).to_have_text("—")
    expect(page.locator("#sources")).to_have_text("—")
    assert page.locator("#provider img").count() == 0
    load(fixture(.2), delay=.35)
    expect(page.locator("#price")).to_have_text("—")
    load(fixture(.6))
    expect(page.locator("#price")).to_have_text("100.25")
    expect(page.locator("#price")).to_have_text("—", timeout=2500)
    assert not errors, errors
    browser.close()
print("Signed-price browser checks passed: review, tampering, request delay, expiry, mobile layout")
