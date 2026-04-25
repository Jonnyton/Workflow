"""Read the host's live Claude.ai chat — full body, scrolled to bottom.

Uses the existing CDP Chrome on localhost:9222. Caller must hold the
browser lock.
"""

import sys

from playwright.sync_api import sync_playwright

CDP = "http://localhost:9222"


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        page = None
        for ctx in browser.contexts:
            for p in ctx.pages:
                page = p
                break
            if page:
                break
        if not page:
            print("no page", file=sys.stderr)
            return 1
        print(f"URL: {page.url}")
        # Scroll to bottom to ensure lazy-loaded messages are present.
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(500)
        # The chat history container in Claude.ai has messages rendered
        # as articles/divs. Grab the main content area text.
        main_loc = page.locator("main")
        body = main_loc.inner_text() if main_loc.count() else page.locator("body").inner_text()
        print(f"LENGTH: {len(body)}")
        # Print the LAST 8000 chars — ascii-safe.
        print("---TAIL---")
        sys.stdout.buffer.write(body[-8000:].encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")
        browser.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
