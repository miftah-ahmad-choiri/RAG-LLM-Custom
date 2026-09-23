"""
excel_parser.py — Reads a TOC Excel (.xlsx) produced by toc_excel.py.

Columns in the TOC sheet (row 1 = header, data from row 2 onwards):
  A  Index       — hierarchical index e.g. "1", "4.1", "12.3.8"
  B  Description — page title (may have leading indent spaces from toc_excel)
  C  URL         — full https URL, stored as HYPERLINK formula
                   (data_only=True makes openpyxl return the evaluated URL string)

Returns:
  {
    "entries":  [{index, description, url, depth, top_index}, ...],
    "sections": [{index, description, url, slug, entry_count}, ...],  # top-level
    "total":    int,
  }
"""

import re
from pathlib import Path
from typing import List, Dict, Any

from openpyxl import load_workbook


def slugify(text: str, max_len: int = 60) -> str:
    """Convert a title string to a filesystem-safe slug.

    Examples:
        "Bootstrapping a new storage cluster" → "bootstrapping-a-new-storage-cluster"
        "NVMe over Fabrics" → "nvme-over-fabrics"
    """
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text[:max_len].rstrip("-")


def _top_index(index: str) -> str:
    """Return the top-level section index from a dotted index string.

    Examples:
        "12.3.8" → "12"
        "4.1"    → "4"
        "1"      → "1"
    """
    return index.split(".")[0]


def parse_excel_toc(xlsx_path: Any) -> Dict:
    """
    Parse the TOC Excel file and return structured data.

    Args:
        xlsx_path: Path (str or Path) to the xlsx file.

    Returns:
        Dict with keys:
          entries  — ordered list of all TOC entries
          sections — list of top-level sections with child counts
          total    — total number of entries
    """
    # Use data_only=False: the workbook was created with HYPERLINK() formulas but no
    # cached values, so data_only=True returns None for the URL column.
    # Instead we read the raw formula string and extract the URL with a regex.
    wb = load_workbook(str(xlsx_path), read_only=True, data_only=False)
    ws = wb["TOC"]

    entries: List[Dict] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < 3:
            continue
        idx, desc, url_raw = row[0], row[1], row[2]
        if not idx or not url_raw:
            continue

        idx  = str(idx).strip()
        desc = str(desc).strip() if desc else idx
        url_raw = str(url_raw).strip()

        # Extract URL from =HYPERLINK("url","url") formula or plain https:// string
        if url_raw.startswith("http"):
            url = url_raw
        else:
            m = re.search(r'"(https?://[^"]+)"', url_raw)
            if m:
                url = m.group(1)
            else:
                continue  # no valid URL — skip this row

        depth = idx.count(".")
        ti    = _top_index(idx)

        entries.append({
            "index":       idx,
            "description": desc,
            "url":         url,
            "depth":       depth,
            "top_index":   ti,
        })

    wb.close()

    # ── Build top-level section summary ──────────────────────────────────────
    # A "top-level" entry has an index with no dots: "1", "12", "31", etc.
    top_map: Dict[str, Dict] = {}
    for e in entries:
        ti = e["top_index"]
        if ti not in top_map:
            # Find the entry whose index == ti (the section's own page)
            top_entry = next((x for x in entries if x["index"] == ti), None)
            label = top_entry["description"] if top_entry else f"Section {ti}"
            top_map[ti] = {
                "index":       ti,
                "description": label,
                "url":         top_entry["url"] if top_entry else "",
                "slug":        slugify(label),
                "entry_count": 0,
            }
        top_map[ti]["entry_count"] += 1

    # Sort by the numeric value of the top-level index (1, 2, 3 … 31)
    sections = sorted(top_map.values(), key=lambda s: int(s["index"]))

    return {
        "entries":  entries,
        "sections": sections,
        "total":    len(entries),
    }
