"""
converter.py — Converts extracted HTML content into clean, structured Markdown.
Preserves headings, code blocks, tables, lists, and paragraphs.
"""

import re
from bs4 import BeautifulSoup, Tag


def _clean_text(text: str) -> str:
    """Normalize whitespace in a text string."""
    return re.sub(r"\s+", " ", text).strip()


def _element_to_markdown(el, depth: int = 0) -> str:
    """Recursively convert a BeautifulSoup element to Markdown."""
    if isinstance(el, str):
        return el

    tag = el.name
    if tag is None:
        return ""

    # ── Headings ──────────────────────────────────────────────────────────────
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        # Offset by depth so sub-page headings don't clash with top-level structure
        md_level = min(level + depth, 6)
        text = _clean_text(el.get_text())
        return f"\n{'#' * md_level} {text}\n"

    # ── Paragraphs ────────────────────────────────────────────────────────────
    if tag == "p":
        text = _inline_elements(el)
        if not text.strip():
            return ""
        return f"\n{text.strip()}\n"

    # ── Code blocks ───────────────────────────────────────────────────────────
    if tag == "pre":
        code_el = el.find("code")
        code_text = (code_el or el).get_text()
        # Try to detect language from class e.g. "language-bash"
        lang = ""
        classes = (code_el or el).get("class", [])
        for cls in classes:
            if cls.startswith("language-"):
                lang = cls.replace("language-", "")
                break
        return f"\n```{lang}\n{code_text.rstrip()}\n```\n"

    if tag == "code":
        # Inline code
        return f"`{el.get_text()}`"

    # ── Lists ─────────────────────────────────────────────────────────────────
    if tag in ("ul", "ol"):
        items = []
        for idx, li in enumerate(el.find_all("li", recursive=False), 1):
            prefix = f"{idx}." if tag == "ol" else "-"
            item_text = _inline_elements(li).strip()
            # Handle nested lists
            nested = li.find(["ul", "ol"])
            if nested:
                nested_md = _element_to_markdown(nested, depth)
                nested_md = "\n".join("  " + ln for ln in nested_md.splitlines())
                items.append(f"{prefix} {item_text}\n{nested_md}")
            else:
                items.append(f"{prefix} {item_text}")
        return "\n" + "\n".join(items) + "\n"

    # ── Tables ────────────────────────────────────────────────────────────────
    if tag == "table":
        return _table_to_markdown(el)

    # ── Blockquotes / Notes / Callouts ────────────────────────────────────────
    if tag == "blockquote":
        inner = _children_to_markdown(el, depth)
        lines = inner.strip().splitlines()
        return "\n" + "\n".join(f"> {ln}" for ln in lines) + "\n"

    # IBM docs often uses div.note / div.tip / div.important
    if tag == "div":
        classes = el.get("class", [])
        note_types = {"note": "📝 **Note:**", "tip": "💡 **Tip:**",
                      "important": "⚠️ **Important:**", "warning": "🚨 **Warning:**",
                      "caution": "⚠️ **Caution:**"}
        for cls, prefix in note_types.items():
            if cls in classes:
                inner = _children_to_markdown(el, depth).strip()
                return f"\n> {prefix} {inner}\n"

    # ── Horizontal rule ───────────────────────────────────────────────────────
    if tag == "hr":
        return "\n---\n"

    # ── Inline elements (bold, italic, links) handled at child level ──────────
    if tag in ("strong", "b"):
        text = _clean_text(el.get_text())
        return f"**{text}**" if text else ""

    if tag in ("em", "i"):
        text = _clean_text(el.get_text())
        return f"*{text}*" if text else ""

    if tag == "a":
        text = _clean_text(el.get_text())
        href = el.get("href", "")
        if href.startswith("http"):
            return f"[{text}]({href})" if text else href
        return text

    # ── Section / article / div — recurse into children ──────────────────────
    if tag in ("div", "section", "article", "main", "aside", "span"):
        return _children_to_markdown(el, depth)

    # ── Default: recurse ──────────────────────────────────────────────────────
    return _children_to_markdown(el, depth)


def _inline_elements(el) -> str:
    """Convert a paragraph-level element, preserving inline formatting."""
    parts = []
    for child in el.children:
        if isinstance(child, str):
            parts.append(child)
        elif hasattr(child, "name"):
            parts.append(_element_to_markdown(child))
    return "".join(parts)


def _children_to_markdown(el, depth: int = 0) -> str:
    """Convert all children of an element to Markdown."""
    parts = []
    for child in el.children:
        if isinstance(child, str):
            text = child.strip()
            if text:
                parts.append(text)
        elif hasattr(child, "name") and child.name:
            parts.append(_element_to_markdown(child, depth))
    return "\n".join(parts)


def _table_to_markdown(table_el) -> str:
    """Convert an HTML <table> to a Markdown table."""
    rows = []
    for tr in table_el.find_all("tr"):
        cells = []
        for cell in tr.find_all(["th", "td"]):
            cells.append(_clean_text(cell.get_text()))
        if cells:
            rows.append(cells)

    if not rows:
        return ""

    # Normalize column count
    max_cols = max(len(r) for r in rows)
    for row in rows:
        while len(row) < max_cols:
            row.append("")

    # Build markdown table
    header = rows[0]
    separator = ["---"] * max_cols
    body = rows[1:]

    def fmt_row(r):
        return "| " + " | ".join(r) + " |"

    lines = [fmt_row(header), fmt_row(separator)]
    lines.extend(fmt_row(r) for r in body)
    return "\n" + "\n".join(lines) + "\n"


def _post_process(md: str) -> str:
    """Clean up the final markdown output."""
    # Collapse 3+ blank lines to 2
    md = re.sub(r"\n{3,}", "\n\n", md)
    # Remove trailing whitespace per line
    md = "\n".join(line.rstrip() for line in md.splitlines())
    return md.strip()


def html_to_markdown(content_html: str, heading_depth_offset: int = 0) -> str:
    """
    Main entry point. Convert a content HTML string to clean Markdown.

    Args:
        content_html: The HTML string of the article content.
        heading_depth_offset: Offset to add to heading levels (avoids clashing
                               with the parent document structure headings).
    Returns:
        A clean Markdown string.
    """
    soup = BeautifulSoup(content_html, "html.parser")

    # Remove IBM feedback / "Was this topic helpful?" widgets
    for el in soup.select(".ibm-feedback, .ibm-helpful, .related-links, "
                           ".shortdesc + .section > .title"):
        el.decompose()

    md = _children_to_markdown(soup, depth=heading_depth_offset)
    return _post_process(md)
