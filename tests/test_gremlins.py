import time
from contextlib import suppress
from pathlib import Path

import pytest

sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright

OUT_DIR = Path(__file__).resolve().parent / "logs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

url = "http://127.0.0.1:8000"
now = int(time.time())
shot = OUT_DIR / f"gremlins_shot_{now}.png"
html = OUT_DIR / f"gremlins_page_{now}.html"
log = OUT_DIR / f"gremlins_console_{now}.log"


def test_gremlins_dashboard():
    """Gremlins-style stress test against the Jarvis dashboard.
    Requires Playwright and a browser (pytest can run this test).
    Outputs: logs/gremlins_console_*.log, gremlins_shot_*.png, gremlins_page_*.html
    """
    with open(log, "w", encoding="utf-8") as logf, sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            pytest.skip(f"Playwright present mais navigateur indisponible : {e}")
        context = browser.new_context()
        page = context.new_page()

        def on_console(msg):
            with suppress(Exception):
                logf.write(f"CONSOLE [{msg.type}] {msg.text}\n")
            logf.flush()

            page.on("console", on_console)
            page.on("pageerror", lambda e: logf.write(f"PAGEERROR: {e}\n"))

            page.goto(url, timeout=30000)
            logf.write(f"Loaded {url}\n")
            logf.flush()

            # Inject gremlins.js from CDN (use jsDelivr which is allowed by CSP)
            page.add_script_tag(url="https://cdn.jsdelivr.net/npm/gremlins.js")
            logf.write("Injected gremlins.js (jsDelivr)\n")
            logf.flush()

            # Launch gremlins for ~20s
            page.evaluate("""
                window._gremlins_done = false;
                (function(){
                    try {
                        var horde = window.gremlins.createHorde({
                            species: [window.gremlins.species.clicker(), window.gremlins.species.formFiller(), window.gremlins.species.typist()],
                        });
                        horde.after(function(){ window._gremlins_done = true; });
                        horde.unleash({duration: 20000});
                    } catch(e) { console.error('gremlins error', e); window._gremlins_done = true; }
                })();
            """)

            # Wait up to 30s for gremlins to finish
            for i in range(30):
                try:
                    done = page.evaluate("() => !!window._gremlins_done")
                except Exception:
                    done = False
                if done:
                    logf.write('Gremlins finished\n')
                    break
                time.sleep(1)
            else:
                logf.write('Gremlins timeout\n')

            # Capture artifacts
            try:
                page.screenshot(path=str(shot), full_page=True)
                logf.write(f"Screenshot saved: {shot}\n")
            except Exception as e:
                logf.write(f"Screenshot failed: {e}\n")

            try:
                html_content = page.content()
                html.write_text(html_content, encoding="utf-8")
                logf.write(f"Page HTML saved: {html}\n")
            except Exception as e:
                logf.write(f"Save HTML failed: {e}\n")

            browser.close()

    # Basic assertion: at least screenshot file should exist
    assert shot.exists(), f"Screenshot not created: {shot}"
