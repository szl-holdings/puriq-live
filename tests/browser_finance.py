"""Native Chromium UI contract against the built container.

Only the research API response is intercepted with explicitly synthetic data.
The production HTML, CSS, JS, Vela distribution and CSP are served unchanged by
that container. This is renderer/interaction evidence, not a live-market test.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from playwright.sync_api import sync_playwright
from puriq_research import ResearchClient

ORIGIN = "http://127.0.0.1:7860"
OUT = ROOT / "finance-evidence"
START = 1782000000 - 1782000000 % 3600


def fixture(pair: str, granularity: int) -> dict:
    start = START - START % granularity
    rows = []
    for i in range(180):
        close = 100 + (i if i < 90 else 180 - i) / 2
        opened = close - .1
        rows.append([start + i * granularity, opened - 1, close + 1, opened, close, 20 + i])
    client = ResearchClient(httpx.MockTransport(lambda _: httpx.Response(200, json=rows)),
                            lambda: start + 301 * granularity)
    return client.history(pair, granularity)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    report = {"schema": "szl.puriq.browser-contract/v1", "source_revision": os.getenv("GITHUB_SHA", "UNBOUND"),
              "fixture_scope": "SYNTHETIC_API_FIXTURE_ONLY_NOT_LIVE_MARKET_DATA",
              "served_application": "built source-bound nonroot Docker container",
              "trading_enabled": False, "deployment_verified": False, "complete": False,
              "viewports": [], "page_errors": [], "unexpected_requests": []}
    page = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            report["browser_version"] = browser.version
            for width, height in ((320, 568), (375, 812), (768, 1024), (1440, 900)):
                context = browser.new_context(viewport={"width": width, "height": height},
                                               reduced_motion="reduce", service_workers="block")
                page = context.new_page()
                page.set_default_timeout(25000)
                page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
                page.on("request", lambda request: report["unexpected_requests"].append(request.url)
                        if urlsplit(request.url).scheme in {"http", "https"} and urlsplit(request.url).hostname != "127.0.0.1" else None)
                mode = {"fail": False}
                def answer(route):
                    if mode["fail"]:
                        route.fulfill(status=503, content_type="application/json", body=json.dumps({
                            "status": "UNAVAILABLE", "reason": "SYNTHETIC_FAILURE_TEST", "trading_enabled": False}))
                    else:
                        query = parse_qs(urlsplit(route.request.url).query)
                        body = fixture(query["pair"][0], int(query["granularity"][0]))
                        route.fulfill(status=200, content_type="application/json", body=json.dumps(body, allow_nan=False))
                page.route(ORIGIN + "/api/puriq/v1/research?*", answer)
                response = page.goto(ORIGIN + "/research", wait_until="networkidle")
                assert response is not None and response.status == 200
                assert "connect-src 'self'" in response.headers["content-security-policy"]
                assert page.locator("#export").is_disabled()
                page.keyboard.press("Tab")
                assert page.locator(".skip").evaluate("element => element === document.activeElement")
                page.locator("#observe").click()
                page.wait_for_function("document.querySelector('#status').textContent.includes('Virtual replay computed')")
                assert page.locator("#pricechart canvas").count() > 0
                assert page.locator("#rows tr").count() == 20
                assert not page.locator("#export").is_disabled()
                assert page.locator("#last").inner_text() == "$100.50"
                assert page.locator("a", has_text="Charts by Vela").is_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f"horizontal overflow at {width}"
                for selector in ("#observe", "#pair", "#granularity"):
                    box = page.locator(selector).bounding_box()
                    assert box and box["height"] >= 44
                with page.expect_download() as pending:
                    page.locator("#export").click()
                download = pending.value
                destination = OUT / f"fixture-export-{width}.json"
                download.save_as(destination)
                exported = json.loads(destination.read_text())
                assert exported["pair"] == "BTC-USD" and exported["trading_enabled"] is False
                assert exported["replay"]["virtual_starting_cash_usd"] == "1000.000000"
                page.evaluate("""() => {const label=document.createElement('aside');label.id='test-fixture-label';
                    label.textContent='TEST FIXTURE — NOT LIVE MARKET DATA';
                    label.style.cssText='position:fixed;top:0;left:0;right:0;z-index:10000;background:#fff;color:#000;text-align:center;font:12px monospace';
                    document.body.append(label);} """)
                page.screenshot(path=str(OUT / f"finance-fixture-{width}.png"), full_page=True)
                page.locator("#pair").select_option("ETH-USD")
                page.locator("#observe").click()
                page.wait_for_function("document.querySelector('#status').textContent.includes('Virtual replay computed')")
                assert page.locator("#rows tr").count() == 20
                mode["fail"] = True
                page.locator("#observe").click()
                page.wait_for_function("document.querySelector('#status').textContent.includes('SYNTHETIC_FAILURE_TEST')")
                assert page.locator("#export").is_disabled()
                assert page.locator("#last").inner_text() == "—"
                assert page.locator("#equity").inner_text() == "—"
                assert page.locator("#pricechart canvas").count() == 0
                assert page.locator("#rows tr").count() == 0
                page.emulate_media(forced_colors="active", reduced_motion="reduce")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                assert page.locator("#observe").is_visible() and page.locator("#observe").is_enabled()
                report["viewports"].append({"width": width, "height": height, "render": "PASS",
                    "rerender": "PASS", "unavailable_clears_stale_results": "PASS", "export": "PASS",
                    "horizontal_overflow": False, "keyboard_skip": "PASS", "touch_height": "PASS",
                    "reduced_motion": True, "forced_colors_controls": "PASS"})
                context.close()
                page = None
            assert not report["page_errors"], report["page_errors"]
            assert not report["unexpected_requests"], report["unexpected_requests"]
            browser.close()
            report["complete"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        if page is not None:
            try:
                page.screenshot(path=str(OUT / "failure-fixture.png"), full_page=True)
            except Exception:
                pass
        raise
    finally:
        (OUT / "browser-contract.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
