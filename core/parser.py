"""
parser.py — Parses IBM-Storage-Ceph-Documentation.md and extracts
the hierarchical structure of headings + URLs.

Kept for backward compatibility. New scraping uses excel_parser.py.
"""

import re
from pathlib import Path
from typing import List, Dict


def parse_doc_file(filepath: str) -> List[Dict]:
    """
    Reads the .md file and returns a list of sections:
    [
        {
            "level": 2,
            "heading": "Getting Started",
            "parent": None,
            "urls": [...],
            "subsections": [...]
        },
        ...
    ]
    """
    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.splitlines()

    url_pattern = re.compile(r"https?://\S+")
    heading_pattern = re.compile(r"^(#{1,6})\s+(.*)")

    root_sections: List[Dict] = []
    stack: List[Dict] = []  # tracks nesting by heading level

    current_section: Dict | None = None

    for line in lines:
        line = line.strip()

        h_match = heading_pattern.match(line)
        if h_match:
            level = len(h_match.group(1))
            heading = h_match.group(2).strip()

            # Skip H1 (document title)
            if level == 1:
                continue

            section: Dict = {
                "level": level,
                "heading": heading,
                "urls": [],
                "subsections": [],
            }

            # Pop stack to find the right parent
            while stack and stack[-1]["level"] >= level:
                stack.pop()

            if stack:
                stack[-1]["subsections"].append(section)
            else:
                root_sections.append(section)

            stack.append(section)
            current_section = section
            continue

        url_match = url_pattern.search(line)
        if url_match and current_section is not None:
            url = url_match.group(0).rstrip(".,;)")
            # Skip malformed/incomplete URLs
            if url.endswith("topic=support-"):
                continue
            if url not in current_section["urls"]:
                current_section["urls"].append(url)

    return root_sections


def flatten_sections(sections: List[Dict]) -> List[Dict]:
    """Flatten nested sections into a list for easy iteration."""
    result = []
    for s in sections:
        result.append(s)
        if s.get("subsections"):
            result.extend(flatten_sections(s["subsections"]))
    return result


def collect_all_urls(sections: List[Dict]) -> List[str]:
    """Collect all unique URLs from the entire tree."""
    seen = set()
    urls = []
    for s in flatten_sections(sections):
        for url in s["urls"]:
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls
