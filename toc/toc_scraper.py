"""
toc_scraper.py — Fetches the FULLY-EXPANDED sidebar TOC from an IBM Docs page.

IBM Docs is a React SPA. The sidebar is lazy-loaded — children only appear in
the DOM after their parent's expand arrow (div.ibmdocs-expand-icon.icon-down)
is clicked. Sub-topics can have their own arrows (3+ levels deep).

Expand strategy:
  1. Navigate and wait for ul.ibmdocs-toc-links to hydrate.
  2. Run an expand loop:
       • Find every icon-down arrow by its parent <li>'s topic-id attribute
         (used as a stable key across retries).
       • For each unseen/un-expanded arrow: click it, wait for children via
         page.wait_for_function polling every 100ms.
       • Per arrow: retry up to MAX_CLICK_RETRIES times.
       • After all retries fail: mark as SKIPPED and log it clearly.
       • Repeat the full loop until no new icon-down arrows appear.
  3. Capture HTML, walk the fully-expanded DOM recursively.
  4. Assign 1.x.x hierarchical indices.

Returns:
  List of { index, description, url, depth }
  Plus (on job object): skipped list for user investigation.
"""

import asyncio
import logging
from typing import Optional, Callable, List, Dict, Set
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

TOC_WAIT_SELECTOR = "ul.ibmdocs-toc-links"

# IBM uses TWO different DOM patterns for the collapse/expand arrow:
#
#  Pattern A — wrapper div carries the state class (most sections):
#    <div class="ibmdocs-toc-row">
#      <a class="ibmdocs-toc-link">…</a>
#      <div class="ibmdocs-expand-icon icon-down">   ← div has icon-down
#        <svg class="ibmdocs-expand-icon">…</svg>
#      </div>
#    </div>
#
#  Pattern B — bare SVG directly in the row (some sections, e.g. Release notes):
#    <div class="ibmdocs-toc-row">
#      <a class="ibmdocs-toc-link">…</a>
#      <svg class="ibmdocs-expand-icon">…</svg>  ← no wrapper div, no icon-down
#    </div>
#
# For Pattern B the row itself has aria-expanded="false" when collapsed.
# We match BOTH patterns so nothing is missed.

# Rows that still need expanding (Pattern A OR Pattern B)
EXPAND_ROW_SEL = (
    # Pattern A: row contains a div.ibmdocs-expand-icon.icon-down
    "ul.ibmdocs-toc-links div.ibmdocs-toc-row:has(div.ibmdocs-expand-icon.icon-down)"
    ", "
    # Pattern B: row contains the bare SVG icon AND has aria-expanded=false
    "ul.ibmdocs-toc-links div.ibmdocs-toc-row[aria-expanded='false']:has(svg.ibmdocs-expand-icon)"
)

# Used by JS helpers to check for the presence of a collapsed arrow by key
# Matches the icon-down div (Pattern A) OR the aria-expanded row (Pattern B)
EXPAND_BTN_SEL = (
    "ul.ibmdocs-toc-links div.ibmdocs-expand-icon.icon-down"
    ", "
    "ul.ibmdocs-toc-links div.ibmdocs-toc-row[aria-expanded='false']:has(svg.ibmdocs-expand-icon)"
)

CHILDREN_TIMEOUT_MS = 8000   # max ms to wait for children to appear after a click
MAX_CLICK_RETRIES   = 2      # attempts per arrow — retry once on timeout
MAX_OUTER_ROUNDS    = 30     # outer loop cap (each round finds newly revealed arrows)


# ── JS helpers (all run inside the browser — no cross-boundary DOM handles) ──
#
# IMPORTANT: page.evaluate() serialises the return value to JSON.
# That means you CANNOT return a DOM element and pass it back in.
# All DOM traversal must happen inside a single evaluate() call.
# ─────────────────────────────────────────────────────────────────────────────

# ── JS read-only helpers (return JSON-serialisable values only) ──────────────
#
# Rule: page.evaluate() serialises its return value to JSON.
#       NEVER return a DOM element — pass it back to Python and try to use it.
#       These helpers only return strings / booleans / null.

# Return the stable string key for the <li> that owns `el`
_JS_GET_KEY = """
(el) => {
    while (el && el.tagName !== 'LI') el = el.parentElement;
    if (!el) return null;
    const row = el.querySelector('[id^="toc-node-"]');
    if (row) return row.id;
    const a = el.querySelector('a[href]');
    return a ? a.getAttribute('href') : null;
}
"""

# Return the visible link text for the <li> that owns `el`
_JS_GET_LABEL = """
(el) => {
    while (el && el.tagName !== 'LI') el = el.parentElement;
    if (!el) return null;
    const a = el.querySelector('a.ibmdocs-toc-link');
    return a ? a.textContent.trim() : null;
}
"""

# Return true if React has responded to the expand click for key `k`.
# Checks TWO success signals:
#   1. The .ibmdocs-toc-children container has <li> children (most sections).
#   2. The <a aria-expanded> toggled to "true" (sections like Glossary that
#      set aria-expanded on the link instead of injecting children immediately).
# (used AFTER the Playwright click to check whether React responded)
_JS_CHILDREN_EXIST = """
(k) => {
    const arrows = document.querySelectorAll(
        'ul.ibmdocs-toc-links [id^="toc-node-"]'
    );
    for (const row of arrows) {
        if (row.id !== k) continue;
        const li = row.closest('li');
        if (!li) return false;
        // Signal 1: children injected
        const container = li.querySelector('.ibmdocs-toc-children');
        if (container && container.querySelector('li')) return true;
        // Signal 2: <a aria-expanded="true"> (IBM uses this on some sections)
        const a = li.querySelector('a.ibmdocs-toc-link');
        if (a && a.getAttribute('aria-expanded') === 'true') return true;
        return false;
    }
    return false;
}
"""

# Return true if NO collapsed arrow with key `k` is present in the sidebar.
# Checks both DOM patterns (Pattern A: icon-down div, Pattern B: aria-expanded row).
_JS_ARROW_GONE = """
(k) => {
    // Pattern A: div.ibmdocs-expand-icon.icon-down
    // Pattern B: div.ibmdocs-toc-row[aria-expanded=false] with svg.ibmdocs-expand-icon
    const selA = 'ul.ibmdocs-toc-links div.ibmdocs-expand-icon.icon-down';
    const selB = "ul.ibmdocs-toc-links div.ibmdocs-toc-row[aria-expanded='false']:has(svg.ibmdocs-expand-icon)";

    for (const sel of [selA, selB]) {
        for (const el of document.querySelectorAll(sel)) {
            let li = el;
            while (li && li.tagName !== 'LI') li = li.parentElement;
            if (!li) continue;
            const rowEl = li.querySelector('[id^="toc-node-"]');
            const key = rowEl ? rowEl.id
                               : (li.querySelector('a[href]') || {}).getAttribute?.('href');
            if (key === k) return false;   // still present — not gone
        }
    }
    return true;   // not found in either pattern → gone / already expanded
}
"""


# ── Hierarchy index builder ───────────────────────────────────────────────────

def _build_indices(entries: List[Dict]) -> List[Dict]:
    """Assign 1.x.x indices based on `depth`."""
    counters: List[int] = []
    prev_depth = -1

    for entry in entries:
        depth = entry["depth"]
        if depth > prev_depth:
            while len(counters) < depth:
                counters.append(0)
            counters.append(1)
        elif depth == prev_depth:
            counters[-1] += 1
        else:
            counters = counters[: depth + 1]
            counters[-1] += 1

        entry["index"] = ".".join(str(c) for c in counters)
        prev_depth = depth

    return entries


# ── Recursive DOM walker ──────────────────────────────────────────────────────

def _walk_ul(ul_tag: Tag, base: str, depth: int, entries: List[Dict]) -> None:
    """
    Recursively walk a <ul> collecting every ibmdocs-toc-link anchor.
    Depth is tracked by <ul> recursion level.
    """
    for li in ul_tag.find_all("li", recursive=False):

        # Grab this <li>'s own anchor — not its children's anchors
        anchor = None
        row_div = li.find("div", class_="ibmdocs-toc-row")
        if row_div:
            anchor = row_div.find("a", class_="ibmdocs-toc-link")

        if anchor is None:
            # Fallback: detach children container, find anchor, reattach
            children_div = li.find("div", class_="ibmdocs-toc-children")
            if children_div:
                children_div.extract()
            anchor = li.find("a", class_="ibmdocs-toc-link")
            if children_div:
                li.append(children_div)

        if anchor:
            href = anchor.get("href", "").strip()
            desc = anchor.get_text(strip=True)
            if href and desc:
                full_url = href if href.startswith("http") else urljoin(base, href)
                entries.append({
                    "depth":       depth,
                    "description": desc,
                    "url":         full_url,
                    "index":       "",
                })

        # Recurse into children
        children_div = li.find("div", class_="ibmdocs-toc-children")
        if children_div:
            child_ul = children_div.find("ul")
            if child_ul:
                _walk_ul(child_ul, base, depth + 1, entries)


# JS that:
#  1. Finds the click target within the row — the inner <svg> element.
#     WHY the SVG, not the wrapper div:
#       The wrapper div.ibmdocs-expand-icon.icon-down may be taller than its
#       inner SVG (e.g. 48px div vs 16px SVG). Clicking the div centre can land
#       in the padding area between the SVG and the div edge — React ignores
#       these coordinates.  The SVG is the actual React pointer-event target.
#  2. Scrolls ALL ancestor overflow containers so the icon is in the viewport.
#  3. Checks that no overlay (e.g. cookie consent banner) is covering the target.
#  4. Returns the SVG's centre coords for page.mouse.click().
#
# IMPORTANT: we click the SVG, not the row centre.
# The row spans the full sidebar width — its centre lands on the <a> link text,
# which navigates to the topic page instead of expanding.
_JS_SCROLL_ICON_INTO_VIEWPORT = """
(rowEl) => {
    // Find the actual click target:
    //   Pattern A: inner <svg> inside div.icon-down  (most sections)
    //   Pattern A fallback: the div.icon-down itself  (if no inner svg)
    //   Pattern B: bare svg.ibmdocs-expand-icon       (some sections)
    const iconDiv = rowEl.querySelector('div.ibmdocs-expand-icon.icon-down');
    const icon = (iconDiv && iconDiv.querySelector('svg'))
               || iconDiv
               || rowEl.querySelector('svg.ibmdocs-expand-icon');
    if (!icon) return { ok: false, reason: 'no-icon' };

    // Scroll every overflow ancestor so the icon enters the visible viewport
    let node = icon.parentElement;
    while (node && node !== document.documentElement) {
        const st = window.getComputedStyle(node);
        const ov = st.overflow + ' ' + st.overflowY;
        if ((ov.includes('scroll') || ov.includes('auto')) && node.scrollHeight > node.clientHeight) {
            const iconRect = icon.getBoundingClientRect();
            const nodeRect = node.getBoundingClientRect();
            node.scrollTop += (iconRect.top + iconRect.height / 2)
                              - (nodeRect.top + nodeRect.height / 2);
        }
        node = node.parentElement;
    }
    // Native scrollIntoView handles the page body
    icon.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });

    // Return the SVG's centre in the viewport AFTER scrolling
    const r = icon.getBoundingClientRect();
    if (!r.width || !r.height) return { ok: false, reason: 'zero-rect' };

    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;

    // Sanity-check: make sure no overlay is covering our click target.
    // If the topmost element at those coords isn't our icon (or its child),
    // something else (e.g. cookie banner) is in the way — report it.
    const topEl = document.elementFromPoint(cx, cy);
    const covered = topEl && !icon.contains(topEl) && !topEl.contains(icon);

    return { x: cx, y: cy, ok: true, covered, coveredBy: covered ? topEl.className : null };
}
"""


# JS: dismiss cookie-consent / truste overlay banners that cover the sidebar.
#
# IMPORTANT: only target well-known consent elements — DO NOT use generic
# selectors like [aria-label="Close"] or .cds--modal-close because IBM Docs
# uses those on the sidebar panel itself and clicking them hides the TOC.
_JS_DISMISS_OVERLAYS = """
() => {
    const dismissed = [];
    // TrustArc / truste consent buttons (very specific IDs — safe to click)
    for (const sel of ['#truste-consent-button', '#truste-consent-required',
                        '.truste-button2', '#consent-accept-btn',
                        '#onetrust-accept-btn-handler', '.cookie-accept']) {
        const btn = document.querySelector(sel);
        if (btn && btn.offsetParent !== null) {
            btn.click();
            dismissed.push(sel);
        }
    }
    // Remove truste/onetrust overlay DOM nodes entirely (safest approach —
    // these are known consent banner containers, not IBM Docs UI elements)
    for (const sel of ['#truste-consent-track', '#truste-overlay', '#teconsent',
                        '.truste-overlay', '#consent_blackbar',
                        '#onetrust-banner-sdk', '#onetrust-consent-sdk']) {
        const el = document.querySelector(sel);
        if (el) { el.remove(); dismissed.push('removed:' + sel); }
    }
    return dismissed;
}
"""


# ── Core expand-all ───────────────────────────────────────────────────────────

async def _dismiss_overlays(page, log: Callable) -> None:
    """Dismiss cookie consent banners / modal overlays that block sidebar clicks."""
    try:
        dismissed = await page.evaluate(_JS_DISMISS_OVERLAYS)
        if dismissed:
            log(f"  🍪 Dismissed overlay(s): {dismissed}")
    except Exception:
        pass


async def _click_arrow_by_key(page, key: str) -> Optional[str]:
    """
    Find the icon-down arrow row by key, scroll ALL ancestors so the element
    lands in the physical browser viewport, then use page.mouse.click() at
    its real screen coordinates.

    WHY page.mouse.click() and not dispatch_event / arrow.click():
      IBM's sidebar React component only responds to real OS-level pointer
      events (pointerdown → mousedown → pointerup → mouseup → click) at actual
      screen coordinates.  Synthetic events — whether from JS element.click(),
      Playwright dispatch_event, or Playwright arrow.click() on an off-screen
      element — are either ignored by React or fail Playwright's actionability
      check.  page.mouse.click(x, y) bypasses all actionability checks and
      fires the exact same event sequence a human produces.

    We click the inner <svg>, not the wrapper div — the svg is the React
    pointer-event target.  The wrapper div may have extra padding whose centre
    falls outside the SVG, causing React to ignore the event.
    """
    rows = await page.query_selector_all(EXPAND_ROW_SEL)
    for row in rows:
        try:
            k = await page.evaluate(_JS_GET_KEY, row)
            if k != key:
                continue

            label = await page.evaluate(_JS_GET_LABEL, row) or key

            # Scroll overflow ancestors + page so the SVG icon is in the
            # viewport, then return its centre coords
            coords = await page.evaluate(_JS_SCROLL_ICON_INTO_VIEWPORT, row)
            if not coords or not coords.get("ok"):
                continue

            # If an overlay is covering the click target, try to dismiss it
            if coords.get("covered"):
                await _dismiss_overlays(page, lambda msg: None)
                # Re-scroll and get fresh coords after overlay removal
                await asyncio.sleep(0.3)
                coords = await page.evaluate(_JS_SCROLL_ICON_INTO_VIEWPORT, row)
                if not coords or not coords.get("ok"):
                    continue

            await asyncio.sleep(0.15)   # let layout repaint after scroll

            # Real OS-level mouse click precisely on the SVG expand icon
            await page.mouse.click(coords["x"], coords["y"])
            return label
        except Exception:
            pass
    return None   # row not found — section already expanded


async def _expand_all(page, log: Callable) -> List[Dict]:
    """
    Expand every collapsed arrow in the sidebar using Playwright real clicks.

    Strategy per arrow:
      1. Find the arrow by stable key, scroll into view, Playwright.click().
      2. Use page.wait_for_function(_JS_CHILDREN_EXIST, key) to wait until
         React has injected child <li> elements OR aria-expanded turns "true".
      3. Retry up to MAX_CLICK_RETRIES times — if all fail, mark as SKIPPED.
      4. Outer loop repeats until no new keys are found (newly revealed arrows
         from expanding parents are picked up in the next round).

    Returns list of skipped { key, description, reason } dicts.
    """
    expanded_keys: Set[str] = set()
    failed_keys:   Set[str] = set()
    skipped:       List[Dict] = []
    total_expanded = 0

    # Dismiss cookie consent banners before starting — they can float over the
    # sidebar at certain scroll positions and intercept mouse clicks.
    await _dismiss_overlays(page, log)

    for outer_round in range(1, MAX_OUTER_ROUNDS + 1):
        # Re-dismiss overlays each round in case they reappear
        await _dismiss_overlays(page, log)


        # ── Collect all unprocessed collapsed rows (present in DOM) ──────────
        # Query EXPAND_ROW_SEL (div.ibmdocs-toc-row containing icon-down) so we
        # discover rows that need expanding.  No is_visible() — off-screen items
        # inside the sidebar overflow container pass DOM presence but may fail
        # is_visible() due to scroll clipping.
        raw_rows      = await page.query_selector_all(EXPAND_ROW_SEL)
        pending_keys: List[tuple] = []          # (key, label)
        for row in raw_rows:
            try:
                key   = await page.evaluate(_JS_GET_KEY,   row)
                label = await page.evaluate(_JS_GET_LABEL, row) or key
                if key and key not in expanded_keys and key not in failed_keys:
                    pending_keys.append((key, label))
            except Exception:
                pass

        # ── If no new rows, do one final settle check ─────────────────────────
        if not pending_keys:
            await asyncio.sleep(0.8)
            raw_rows = await page.query_selector_all(EXPAND_ROW_SEL)
            for row in raw_rows:
                try:
                    key   = await page.evaluate(_JS_GET_KEY,   row)
                    label = await page.evaluate(_JS_GET_LABEL, row) or key
                    if key and key not in expanded_keys and key not in failed_keys:
                        pending_keys.append((key, label))
                except Exception:
                    pass
            if not pending_keys:
                log(f"✅ Sidebar fully expanded — "
                    f"{total_expanded} opened, {len(skipped)} skipped.")
                return skipped

        log(f"🔽 Round {outer_round}: {len(pending_keys)} section(s) to expand…")

        for key, label in pending_keys:
            success     = False
            last_reason = "unknown"
            last_label  = label

            for attempt in range(1, MAX_CLICK_RETRIES + 1):
                try:
                    # ── Step 1: check if already expanded ────────────────────
                    already = await page.evaluate(_JS_CHILDREN_EXIST, key)
                    if already:
                        success     = True
                        last_reason = "already"
                        break

                    arrow_gone = await page.evaluate(_JS_ARROW_GONE, key)
                    if arrow_gone:
                        success     = True
                        last_reason = "arrow-gone"
                        break

                    # ── Step 2: Playwright real click ─────────────────────────
                    clicked_label = await _click_arrow_by_key(page, key)
                    if clicked_label:
                        last_label = clicked_label
                    else:
                        # Arrow disappeared between the query and the click
                        success     = True
                        last_reason = "arrow-gone"
                        break

                    # ── Step 3: wait for React to inject children ─────────────
                    # Uses page.wait_for_function with the JS predicate that
                    # checks the children container — polling every 100ms.
                    try:
                        await page.wait_for_function(
                            _JS_CHILDREN_EXIST,
                            arg=key,
                            timeout=CHILDREN_TIMEOUT_MS,
                            polling=100,
                        )
                        success     = True
                        last_reason = "expanded"
                        break
                    except Exception:
                        # Timeout — check once more: arrow may have disappeared
                        # (leaf node that has no children to inject)
                        arrow_gone = await page.evaluate(_JS_ARROW_GONE, key)
                        if arrow_gone:
                            success     = True
                            last_reason = "leaf-no-children"
                            break
                        last_reason = "timeout"

                except Exception as exc:
                    last_reason = str(exc)[:120]

            if success:
                expanded_keys.add(key)
                total_expanded += 1
            else:
                failed_keys.add(key)
                skipped.append({
                    "key":         key,
                    "description": last_label,
                    "reason":      last_reason,
                })
                log(f"  ⚠️  SKIPPED: {last_label!r} — {last_reason}")

        # Give React time to inject newly revealed child arrows before next round
        await asyncio.sleep(0.5)

    log(f"⚠️  Round limit ({MAX_OUTER_ROUNDS}) reached. "
        f"Expanded: {total_expanded}, Skipped: {len(skipped)}.")
    return skipped


# ── Core async scraper ────────────────────────────────────────────────────────

async def _fetch_toc_async(
    url: str,
    on_log: Optional[Callable] = None,
) -> Dict:
    """
    Returns { "entries": [...], "skipped": [...] }
    """
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    def log(msg: str):
        logger.info(msg)
        if on_log:
            on_log(msg)

    parsed = urlparse(url)
    base   = f"{parsed.scheme}://{parsed.netloc}"

    log(f"🌐 Opening browser for: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--window-size=1440,900"],
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=BROWSER_UA,
            locale="en-US",
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        try:
            log("📄 Navigating to page…")
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            if resp and resp.status == 403:
                raise RuntimeError(
                    f"IBM WAF returned 403 for {url}. "
                    "Open the page manually in a real browser first."
                )

            log("⏳ Waiting for sidebar to hydrate…")
            try:
                await page.wait_for_selector(TOC_WAIT_SELECTOR, timeout=20000)
            except Exception:
                raise RuntimeError(
                    "Sidebar (ul.ibmdocs-toc-links) never appeared. "
                    "Make sure the URL is an IBM Docs product page."
                )

            await asyncio.sleep(1.5)   # let initial render settle

            log("🔽 Expanding all sidebar sections (with retry per section)…")
            skipped = await _expand_all(page, log)

            await asyncio.sleep(1.0)   # final settle

            html = await page.content()
            log("📥 Full expanded page source captured.")

        finally:
            await browser.close()

    # ── Parse the fully-expanded HTML ─────────────────────────────────────────
    log("🔍 Parsing sidebar tree…")
    soup     = BeautifulSoup(html, "html.parser")
    toc_root = soup.select_one("ul.ibmdocs-toc-links")
    if not toc_root:
        raise RuntimeError(
            "Could not find ul.ibmdocs-toc-links in the captured HTML."
        )

    raw_entries: List[Dict] = []
    _walk_ul(toc_root, base, depth=0, entries=raw_entries)

    log(f"🔗 Found {len(raw_entries)} TOC entries.")
    _build_indices(raw_entries)

    from collections import Counter
    depth_counts = Counter(e["depth"] for e in raw_entries)
    summary = "  |  ".join(
        f"depth-{d}: {c}" for d, c in sorted(depth_counts.items())
    )
    log(f"📊 Depth breakdown — {summary}")

    if skipped:
        log(f"⚠️  {len(skipped)} section(s) could not be expanded (logged below):")
        for s in skipped:
            log(f"    • {s['description']!r}  [{s['key']}]  reason: {s['reason']}")

    return {"entries": raw_entries, "skipped": skipped}


# ── Synchronous entry point for Flask threads ─────────────────────────────────

def fetch_toc(
    url: str,
    on_log: Optional[Callable] = None,
) -> Dict:
    """
    Synchronous wrapper for Flask background threads.
    Returns { "entries": [...], "skipped": [...] }
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_fetch_toc_async(url, on_log=on_log))
    finally:
        loop.close()
        asyncio.set_event_loop(None)
