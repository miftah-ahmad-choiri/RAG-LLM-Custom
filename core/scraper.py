"""
scraper.py — Fetches IBM Storage Ceph documentation pages using Playwright.

Key findings from diagnostics:
  - IBM WAF returns 403 to all headless browsers (Cloudflare/Akamai bot detection)
  - IBM WAF returns 403 to plain requests (no JS session)
  - headless=False (visible browser window) bypasses the WAF and gets HTTP 200
  - wait_until="networkidle" times out — IBM SPA keeps background beacons alive
  - Use wait_until="domcontentloaded" + wait_for_selector() instead

Performance strategy:
  - Open ONE browser + ONE tab for the entire batch (not one browser per URL)
  - Navigate the same tab to each URL sequentially — much faster
  - on_result callback fires immediately after each page so output is written
    to disk right away — no need to wait for all pages to finish
"""

import asyncio
import logging
from typing import Optional, Callable

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# CSS selectors for IBM docs main article content (priority order)
IBM_CONTENT_SELECTORS = [
    "article",
    "main",
    "[role='main']",
    "div.ibm-content-body",
    "div.content",
    "div#content",
]

# Wait for this selector before grabbing HTML (proves React has hydrated)
IBM_WAIT_SELECTOR = "main, article, [role='main'], .ibm-content-body"

# Noise to strip from extracted content
IBM_NOISE_SELECTORS = (
    "nav, header, footer, "
    ".ibm-navigation, .ibm-sidebar, .ibm-breadcrumb, .ibm-toc, "
    "script, style, "
    "[role='navigation'], [role='banner'], [role='complementary'], "
    ".feedback-section, .ibm-related-links, .warning-banner, "
    ".cookie-banner, .ibm-masthead, .ibm-header, "
    ".ibm-toc-container, .ibm-table-of-contents"
)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _extract_content_html(html: str) -> str:
    """Extract the main article body from a full rendered page HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.select(IBM_NOISE_SELECTORS):
        tag.decompose()

    for selector in IBM_CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el and len(el.get_text(strip=True)) > 200:
            return str(el)

    body = soup.find("body")
    return str(body) if body else html


async def _scrape_all_async(
    urls: list,
    rate_limit_seconds: float,
    on_result: Callable,
    cancel_check: Callable,
):
    """
    Opens ONE browser and ONE tab, navigates through all URLs sequentially.

    Calls on_result(url, content_html_or_None, index, total) immediately
    after each page — so the caller can write to disk right away without
    waiting for the full batch to complete.

    cancel_check() → True means stop the loop immediately.
    """
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    total = len(urls)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,          # IBM WAF blocks all headless requests
            args=["--window-size=1024,768"],
        )
        context = await browser.new_context(
            viewport={"width": 1024, "height": 768},
            user_agent=BROWSER_UA,
            locale="en-US",
        )
        page = await context.new_page()

        # Stealth patches: removes navigator.webdriver, fixes UA inconsistencies
        await Stealth().apply_stealth_async(page)

        try:
            for i, url in enumerate(urls, 1):
                if cancel_check():
                    logger.info("Scrape batch cancelled by user.")
                    break

                logger.info(f"[{i}/{total}] Navigating: {url}")
                content_html = None

                try:
                    resp = await page.goto(
                        url,
                        wait_until="domcontentloaded",   # networkidle times out on IBM SPA
                        timeout=40000,
                    )

                    if resp and resp.status == 403:
                        logger.warning(f"  403 Forbidden — {url}")
                    else:
                        # Wait for React to render the article body
                        try:
                            await page.wait_for_selector(IBM_WAIT_SELECTOR, timeout=12000)
                        except Exception:
                            logger.warning("  Content selector not found — grabbing page anyway")

                        # Brief settle for any remaining dynamic content
                        await asyncio.sleep(1)

                        html = await page.content()
                        content_html = _extract_content_html(html)

                        text_len = len(
                            BeautifulSoup(content_html, "html.parser").get_text(strip=True)
                        )
                        status = resp.status if resp else "?"
                        logger.info(f"  OK {status} — {text_len} chars")

                except Exception as exc:
                    logger.error(f"  Navigation error: {exc}")

                # Fire the callback immediately — caller writes to file now
                on_result(url, content_html, i, total)

                # Rate limit between pages (skip after last)
                if i < total and not cancel_check():
                    await asyncio.sleep(rate_limit_seconds)

        finally:
            await browser.close()


def scrape_all(
    urls: list,
    rate_limit_seconds: float = 2.0,
    on_result: Optional[Callable] = None,
    cancel_check: Optional[Callable] = None,
):
    """
    Synchronous entry point for Flask background threads.

    Scrapes all URLs with a SINGLE persistent browser session (open once,
    navigate N times, close once). Calls on_result after each page so the
    output file grows incrementally — no waiting for the full batch.

    Args:
        urls:               List of URLs to scrape.
        rate_limit_seconds: Seconds to wait between page navigations.
        on_result:          Callback(url, content_html_or_None, index, total).
                            Called immediately after each page is fetched.
        cancel_check:       Callable() -> bool. Return True to stop the batch.
    """
    if on_result is None:
        on_result = lambda *_: None
    if cancel_check is None:
        cancel_check = lambda: False

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _scrape_all_async(urls, rate_limit_seconds, on_result, cancel_check)
        )
    finally:
        loop.close()
        asyncio.set_event_loop(None)
