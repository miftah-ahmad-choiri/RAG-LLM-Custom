"""
toc_excel.py — Writes the scraped TOC entries to a styled Excel (.xlsx) file.

Columns:
  A  Index        — hierarchical index string  (e.g. "1", "1.3", "1.3.2")
  B  Description  — link text
  C  URL          — full https:// URL (formatted as a clickable hyperlink)

Styling:
  - Header row:      IBM blue background, white bold text, auto-filter enabled
  - Top-level rows:  light-blue fill, bold description
  - Second-level:    very light blue fill
  - Deeper rows:     white
  - Skipped rows:    amber/orange fill on all 3 cells + red bold description
                     + an Excel cell comment on the Index cell explaining why
  - URL column:      real Excel HYPERLINK() formula — clickable
  - Info sheet:      generation metadata + skipped list
"""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment


# ── Colour palette ──────────────────────────────────────────────────────────
HEADER_FILL  = PatternFill("solid", fgColor="0F62FE")   # IBM blue
LEVEL0_FILL  = PatternFill("solid", fgColor="D0E2FF")   # blue-10
LEVEL1_FILL  = PatternFill("solid", fgColor="EDF5FF")   # blue-5
LEVEL2_FILL  = PatternFill("solid", fgColor="FFFFFF")   # white
SKIPPED_FILL = PatternFill("solid", fgColor="FEF3C7")   # amber-100

THIN_BORDER  = Border(bottom=Side(style="thin", color="E2E6EA"))
SKIP_BORDER  = Border(
    top=Side(style="thin", color="F59E0B"),
    bottom=Side(style="thin", color="F59E0B"),
    left=Side(style="thin", color="F59E0B"),
    right=Side(style="thin", color="F59E0B"),
)

HEADER_FONT  = Font(name="Calibri", bold=True,  color="FFFFFF", size=11)
LEVEL0_FONT  = Font(name="Calibri", bold=True,  size=10)
NORMAL_FONT  = Font(name="Calibri",             size=10)
SKIPPED_FONT = Font(name="Calibri", bold=True,  color="92400E", size=10)  # dark amber
LINK_FONT    = Font(name="Calibri",             color="0353E9", size=10, underline="single")
SKIP_LINK    = Font(name="Calibri",             color="B45309", size=10, underline="single")


def _depth_from_index(index: str) -> int:
    return index.count(".")


def _indent(depth: int) -> str:
    return "  " * depth


def write_toc_excel(
    entries: List[Dict],
    output_path: Path,
    skipped: Optional[List[Dict]] = None,
    category_name: str = "",
) -> Path:
    """
    Write *entries* to *output_path* as a styled .xlsx file.

    Args:
        entries:       List of { index, description, url, depth } dicts.
        output_path:   Where to save the file.
        skipped:       Optional list of { key, description, reason } dicts from
                       the scraper. Rows whose description matches a skipped entry
                       are highlighted amber with a cell comment explaining why.
        category_name: Human-readable product/version label stored in the Info
                       sheet so the scraper page can display it (e.g. "IBM Storage
                       Ceph 9.9.1").

    Returns the resolved path.
    """
    skipped = skipped or []

    # Build a lookup: description → reason  (for O(1) row marking)
    # IBM toc-node keys are unique; descriptions are almost always unique too.
    # We key by description because that's what appears in the entry row.
    skipped_map: Dict[str, str] = {}
    for s in skipped:
        skipped_map[s["description"]] = (
            f"⚠️ Could not expand — sub-topics may be missing.\n"
            f"Key:    {s['key']}\n"
            f"Reason: {s['reason']}"
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "TOC"

    # ── Header row ──────────────────────────────────────────────────────────
    ws.append(["Index", "Description", "URL"])
    for cell in ws[1]:
        cell.font      = HEADER_FONT
        cell.fill      = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 22
    ws.auto_filter.ref          = f"A1:C{len(entries) + 1}"
    ws.freeze_panes             = "A2"

    # ── Data rows ────────────────────────────────────────────────────────────
    for row_num, entry in enumerate(entries, start=2):
        idx   = entry["index"]
        desc  = entry["description"]
        url   = entry["url"]
        depth = _depth_from_index(idx)

        is_skipped     = desc in skipped_map
        indented_desc  = _indent(depth) + desc
        hyperlink_cell = f'=HYPERLINK("{url}","{url}")'

        ws.append([idx, indented_desc, hyperlink_cell])
        row = ws[row_num]

        if is_skipped:
            # ── Skipped row: amber fill + orange border + bold dark text ─────
            for cell in row:
                cell.fill   = SKIPPED_FILL
                cell.border = SKIP_BORDER
                cell.alignment = Alignment(vertical="center", wrap_text=False)

            row[0].font      = Font(name="Calibri", bold=True, color="92400E", size=10)
            row[0].alignment = Alignment(horizontal="center", vertical="center")
            row[1].font      = SKIPPED_FONT
            row[2].font      = SKIP_LINK
            row[2].alignment = Alignment(horizontal="left", vertical="center")

            # Cell comment on the Index cell — visible on hover in Excel
            note_text = skipped_map[desc]
            comment   = Comment(note_text, "TOC Scraper")
            comment.width  = 320
            comment.height = 90
            row[0].comment = comment

        else:
            # ── Normal row: depth-based fill ─────────────────────────────────
            if depth == 0:
                fill      = LEVEL0_FILL
                desc_font = LEVEL0_FONT
            elif depth == 1:
                fill      = LEVEL1_FILL
                desc_font = NORMAL_FONT
            else:
                fill      = LEVEL2_FILL
                desc_font = NORMAL_FONT

            for cell in row:
                cell.fill      = fill
                cell.border    = THIN_BORDER
                cell.alignment = Alignment(vertical="center", wrap_text=False)

            row[0].font      = NORMAL_FONT
            row[0].alignment = Alignment(horizontal="center", vertical="center")
            row[1].font      = desc_font
            row[2].font      = LINK_FONT
            row[2].alignment = Alignment(horizontal="left", vertical="center")

        ws.row_dimensions[row_num].height = 18

    # ── Column widths ────────────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 12
    max_desc = max(
        (len(e["description"]) + _depth_from_index(e["index"]) * 2 for e in entries),
        default=20,
    )
    ws.column_dimensions["B"].width = min(max_desc + 4, 62)
    ws.column_dimensions["C"].width = 72

    # ── Info sheet ───────────────────────────────────────────────────────────
    info = wb.create_sheet("Info")
    info_header_font = Font(name="Calibri", bold=True, size=10)

    info.append(["Category",        category_name or ""])
    info.append(["Generated",       datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    info.append(["Total entries",   len(entries)])
    info.append(["Top-level",       sum(1 for e in entries if "." not in e["index"])])
    info.append(["Skipped sections",len(skipped)])
    info.column_dimensions["A"].width = 22
    info.column_dimensions["B"].width = 44

    for cell in info["A"]:
        cell.font = info_header_font

    if skipped:
        info.append([])   # blank row
        info.append(["#", "Skipped Section", "Key (toc-node ID)", "Failure Reason"])
        skip_hdr_row = info.max_row
        for cell in info[skip_hdr_row]:
            cell.font = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
            cell.fill = PatternFill("solid", fgColor="B45309")  # amber-700
            cell.alignment = Alignment(horizontal="center")

        info.column_dimensions["C"].width = 38
        info.column_dimensions["D"].width = 48

        for i, s in enumerate(skipped, start=1):
            info.append([i, s["description"], s["key"], s["reason"]])
            skip_row = info[info.max_row]
            for cell in skip_row:
                cell.fill      = PatternFill("solid", fgColor="FEF3C7")
                cell.font      = Font(name="Calibri", size=10)
                cell.alignment = Alignment(vertical="center")
            skip_row[1].font = Font(name="Calibri", bold=True, color="92400E", size=10)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_path))
    return output_path.resolve()
