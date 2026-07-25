"""Gremlins-style stress test against the Jarvis dashboard.

This is a manual test script, not part of the automated pytest suite.
Requires Playwright and a browser to be installed.

Usage:
    python scripts/manual_tests/gremlins.py

The script will:
- Start a headless Chromium browser
- Navigate to http://127.0.0.1:8000
- Inject gremlins.js from CDN
- Run gremlins for ~20 seconds (clicker, form filler, typist species)
- Capture screenshot, HTML, and console logs to logs/ directory
"""
import sys
import time
from contextlib import suppress
from pathlib import Path

# Check for Playwright
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: Playwright is not installed.")
    print("Install it with: pip install playwright")
    print("Then run: playwright install chromium")
    sys.exit(1)

OUT_DIR = Path(__file__).resolve().parent.parent / "logs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

url = "http://127.0.0.1:8000"
now = int(time.time())
shot = OUT_DIR / f"gremlins_shot_{now}.png"
html_file = OUT_DIR / f"gremlins_page_{now}.html"
log_file = OUT_DIR / f"gremlins_console_{now}.log"


def main():
    print(f"Starting Gremlins stress test against {url}")
    print(f"Logs will be saved to: {log_file}")

    with open(log_file, "w", encoding="utf-8") as logf:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                print(f"ERROR: Failed to launch browser: {e}")
                logf.write(f"ERROR: Failed to launch browser: {e}\n")
                return 1

            context = browser.new_context()
            page = context.new_page()

            def on_console(msg):
                with suppress(Exception):
                    logf.write(f"CONSOLE [{msg.type}] {msg.text}\n")
                logf.flush()

            page.on("console", on_console)
            page.on("pageerror", lambda e: logf.write(f"PAGEERROR: {e}\n"))

            try:
                page.goto(url, timeout=30000)
                logf.write(f"Loaded {url}\n")
                logf.flush()

                # Inject gremlins.js from CDN
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
                    html_file.write_text(html_content, encoding="utf-8")
                    logf.write(f"Page HTML saved: {html_file}\n")
                except Exception as e:
                    logf.write(f"Save HTML failed: {e}\n")

                browser.close()
                print(f"SUCCESS: Gremlins test completed. Artifacts saved to {OUT_DIR}")
                return 0

            except Exception as e:
                logf.write(f"ERROR: {e}\n")
                print(f"ERROR: {e}")
                browser.close()
                return 1


if __name__ == "__main__":
    sys.exit(main())
