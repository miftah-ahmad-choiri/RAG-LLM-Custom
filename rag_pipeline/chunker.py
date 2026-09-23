"""
Ceph-aware hierarchical chunking for IBM Storage Ceph documentation.

Strategy:
- Parse Markdown heading hierarchy (# ## ### ####)
- Each section becomes a chunk with full heading path metadata
- Oversized chunks split at paragraph boundaries with overlap
- Ceph-specific topic tags extracted from content
- Content type classified (procedure/concept/reference/troubleshooting)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
import tiktoken


@dataclass
class Chunk:
    """Represents a document chunk with metadata."""
    text: str
    metadata: Dict
    token_count: int


# ─── Tokenizer (singleton) ───────────────────────────────────────────────
_encoder = None


def get_encoder() -> tiktoken.Encoding:
    """Get or create cl100k_base encoder (GPT-4 / BGE compatible)."""
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def estimate_tokens(text: str) -> int:
    """Estimate token count for text."""
    return len(get_encoder().encode(text))


# ─── Ceph-Specific Keywords for Topic Tagging ────────────────────────────
CEPH_KEYWORDS = [
    # Core components
    "osd", "monitor", "mgr", "mds", "rgw", "crush", "pg", "pool",
    "bluestore", "rocksdb", "bluefs",
    # Data protection
    "erasure", "replication", "device-class", "crush-rule",
    # Deployment
    "cephadm", "ansible", "bootstrap", "dashboard",
    # Storage types
    "rbd", "cephfs", "nfs", "smb", "nvme", "iscsi",
    # Operations
    "stretch", "upgrade", "keyring", "cephx", "auth",
    "encryption", "compression", "scrub", "recovery",
    "backfill", "peering", "degraded", "misplaced", "clean", "active",
    # Hardware
    "hdd", "ssd", "nvme",
    # Configuration
    "config", "option", "parameter", "setting",
]


def extract_topic_tags(text: str) -> List[str]:
    """Extract Ceph-specific keywords from text as topic tags."""
    text_lower = text.lower()
    tags = [kw for kw in CEPH_KEYWORDS if kw in text_lower]
    # ChromaDB doesn't allow empty lists, return a default if no tags found
    return tags if tags else ["general"]


# Structural IBM docs section headings that are always "concept" type,
# regardless of what words appear in their body text.
# e.g. "About this task" often contains words like "fails" or "error"
# which would incorrectly classify it as troubleshooting.
_CONCEPT_HEADINGS = frozenset({
    "about this task",
    "before you begin",
    "prerequisites",
    "overview",
    "introduction",
    "what to do next",
    "results",
    "background",
    "context",
})


def classify_content_type(text: str, heading: str = "") -> str:
    """Classify chunk content type for retrieval filtering.

    Args:
        text:    Full chunk text.
        heading: The section's own title. When it matches a known structural
                 IBM docs heading, the classification is fixed to 'concept'
                 regardless of body content.
    """
    # Structural headings are always concept — they describe context, not
    # executable steps, even when their body incidentally mentions errors
    # or commands (e.g. "About this task" that says "bootstrapping fails").
    if heading.lower().strip() in _CONCEPT_HEADINGS:
        return "concept"

    text_lower = text.lower()

    # Procedure indicators (commands, steps, how-to)
    if any(kw in text_lower for kw in [
        "ceph osd", "ceph tell", "ceph daemon", "ceph config",
        "ceph pg", "ceph pool", "ceph auth", "ceph crush",
        "run the following", "execute", "command:", "step 1",
        "procedure", "how to", "to create", "to set", "to add",
        "to remove", "to configure", "to enable", "to disable"
    ]):
        return "procedure"

    # Troubleshooting indicators
    if any(kw in text_lower for kw in [
        "error", "fail", "troubleshoot", "debug", "issue",
        "problem", "resolve", "fix", "stuck", "degraded",
        "down", "slow", "timeout", "hang", "crash"
    ]):
        return "troubleshooting"

    # Reference indicators (tables, options, parameters)
    if any(kw in text_lower for kw in [
        "option", "parameter", "setting", "config", "default",
        "range", "table", "flag", "value", "limit", "threshold"
    ]):
        return "reference"

    return "concept"


# ─── Heading Parsing ─────────────────────────────────────────────────────

def parse_headings(md_text: str) -> List[Dict]:
    """Extract heading hierarchy from markdown text."""
    headings = []
    for i, line in enumerate(md_text.split('\n')):
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            headings.append({
                "level": len(match.group(1)),
                "title": match.group(2).strip(),
                "line": i
            })
    return headings


# ─── Glossary / Terminology Chunking ────────────────────────────────────

def _is_glossary_file(file_path: str, md_text: str) -> bool:
    """Detect files that are glossary/terminology pages.

    These files have no sub-headings — terms are defined as bold-word
    paragraphs.  The heading-based chunker would lump them all into one
    giant chunk, diluting every individual term's embedding.
    """
    path_lower = file_path.lower()
    if any(kw in path_lower for kw in ("terminology", "glossary", "definitions", "terms")):
        return True
    # Heuristic: many lines that are just a standalone bold/plain word
    # followed by a definition paragraph, with no sub-headings at all.
    lines = md_text.split('\n')
    headings = [l for l in lines if re.match(r'^#{2,6}\s', l)]
    bold_terms = [l for l in lines if re.match(r'^\*{1,2}[A-Z][^*\n]{1,60}\*{1,2}\s*$', l)]
    # If no sub-headings but many bold term lines → glossary-style
    return len(headings) == 0 and len(bold_terms) >= 5


def _chunk_glossary(
    md_text: str,
    file_path: str,
    min_chunk_tokens: int = 30,
) -> List[Chunk]:
    """Split a flat glossary file into one chunk per definition term.

    Splits on lines that are either:
    - A standalone bold term:  **Term**  or  *Term*
    - A bare capitalised word on its own line (like the IBM terminology page)
    followed by one or more paragraphs of definition text.

    Each resulting chunk contains:
        # Terminology > <Term>

        <definition text>
    so the heading prefix carries the term name into the embedding.
    """
    lines = md_text.split('\n')

    # Collect file-level parents from the first heading (if any)
    file_heading = "Terminology"
    for line in lines:
        m = re.match(r'^#{1,2}\s+(.+)$', line)
        if m:
            file_heading = m.group(1).strip()
            break

    # Extract chapter from file path
    chapter_match = re.search(r'(\d+-[^/\\]+)', file_path)
    chapter = chapter_match.group(1) if chapter_match else "unknown"

    # A "term starter" line: standalone bold, or a plain capitalised word
    # with no punctuation that is immediately followed by a definition.
    term_pattern = re.compile(
        r'^\*{1,2}([A-Z][^*\n]{0,80})\*{1,2}\s*$'   # **Term** or *Term*
        r'|^([A-Z][A-Za-z /\-()]{1,60})\s*$'          # Plain capitalised word
    )

    chunks: List[Chunk] = []
    current_term: Optional[str] = None
    current_lines: List[str] = []

    def _flush(term: str, body_lines: List[str]) -> None:
        body = '\n'.join(body_lines).strip()
        if not body:
            return
        section = {
            "level": 2,
            "title": term,
            "parents": [file_heading],
        }
        embedded_text = f"# {file_heading} > {term}\n\n{body}"
        if estimate_tokens(embedded_text) < min_chunk_tokens:
            return
        metadata = {
            "source_file": file_path,
            "chapter": chapter,
            "section_number": "",
            "heading_path": f"{file_heading} > {term}",
            "heading_level": 2,
            "title": term,
            "topic_tags": extract_topic_tags(body),
            "content_type": "reference",   # glossary entries are always reference
            "ceph_version": "9.9.1",
            "product": "IBM Storage Ceph",
        }
        chunks.append(Chunk(
            text=embedded_text,
            metadata=metadata,
            token_count=estimate_tokens(embedded_text),
        ))

    for line in lines:
        # Skip the top-level heading and source footer lines
        if re.match(r'^#{1,2}\s', line) or re.match(r'^\*Source:', line) or \
                re.match(r'^>\s*\*\*(?:Index|Source):', line) or line.strip() == '---':
            continue

        m = term_pattern.match(line.strip())
        if m:
            # Flush previous term
            if current_term and current_lines:
                _flush(current_term, current_lines)
            current_term = (m.group(1) or m.group(2)).strip()
            current_lines = []
        elif current_term is not None:
            current_lines.append(line)

    # Flush final term
    if current_term and current_lines:
        _flush(current_term, current_lines)

    return chunks


# ─── Main Chunking Function ──────────────────────────────────────────────

def chunk_markdown(
    md_text: str,
    file_path: str,
    max_tokens: int = 512,
    overlap_tokens: int = 50,
    min_chunk_tokens: int = 30
) -> List[Chunk]:
    """
    Chunk markdown by heading hierarchy.

    Args:
        md_text: Full markdown content
        file_path: Relative path for metadata
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlap between split chunks
        min_chunk_tokens: Minimum tokens to keep a chunk

    Returns:
        List of Chunk objects with text and metadata
    """
    # Delegate to the glossary chunker for terminology/definition pages
    if _is_glossary_file(file_path, md_text):
        return _chunk_glossary(md_text, file_path, min_chunk_tokens)

    # Strip "Copy to clipboard" lines injected by the IBM docs scraper.
    # These appear after every fenced code block and add pure UI noise to
    # chunk embeddings, pulling vectors away from the actual command content.
    md_text = re.sub(r'^Copy to clipboard\s*$', '', md_text, flags=re.MULTILINE)

    lines = md_text.split('\n')
    sections = []  # Completed sections ready for chunking
    section_stack = [{
        "level": 0,
        "title": "ROOT",
        "content": [],
        "start_line": 0,
        "parents": []
    }]

    for i, line in enumerate(lines):
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()

            # Close sections deeper than current level
            while section_stack and section_stack[-1]["level"] >= level:
                closed = section_stack.pop()
                if closed["content"]:
                    chunk_text = '\n'.join(closed["content"])
                    if estimate_tokens(chunk_text) >= min_chunk_tokens:
                        sections.append((chunk_text, closed))

            # Start new section
            section_stack.append({
                "level": level,
                "title": title,
                "content": [line],
                "start_line": i,
                "parents": [s["title"] for s in section_stack[1:]]  # Skip ROOT
            })
        else:
            # Add content to current deepest section
            if section_stack:
                section_stack[-1]["content"].append(line)

    # Flush remaining sections
    for section in section_stack[1:]:  # Skip ROOT
        if section["content"]:
            chunk_text = '\n'.join(section["content"])
            if estimate_tokens(chunk_text) >= min_chunk_tokens:
                sections.append((chunk_text, section))

    # Create chunks with metadata
    chunks = []
    for text, section in sections:
        chunk = _create_chunk(text, file_path, section)
        chunks.append(chunk)

    # Post-process: split oversized chunks
    return _split_oversized_chunks(chunks, max_tokens, overlap_tokens)


def _create_chunk(text: str, file_path: str, section: Dict) -> Chunk:
    """Create a Chunk with full metadata.

    The heading path is prepended to the chunk text so that the embedding
    model sees the section's full context, not just its body.  This is
    especially important for short sections whose body alone gives the
    model too little signal.

    The prepended prefix uses the format:
        # Chapter > Parent > Title
    which closely mirrors how headings appear in the source markdown.
    """
    # Build heading path: "11-planning > 11.3-storage-strategies > Device Class"
    heading_path = " > ".join(section["parents"] + [section["title"]])

    # Extract chapter from file path (e.g., "11-planning")
    chapter_match = re.search(r'(\d+-[^/]+)', file_path)
    chapter = chapter_match.group(1) if chapter_match else "unknown"

    # Extract section number from heading path (e.g., "11.3.2.4")
    section_num_match = re.search(r'(\d+(?:\.\d+)*)', heading_path)
    section_number = section_num_match.group(1) if section_num_match else ""

    # Prepend heading context to the embedded text so the vector captures
    # the section's topic even when the body is short or generic.
    embedded_text = f"# {heading_path}\n\n{text}"

    metadata = {
        "source_file": file_path,
        "chapter": chapter,
        "section_number": section_number,
        "heading_path": heading_path,
        "heading_level": section["level"],
        "title": section["title"],
        "topic_tags": extract_topic_tags(text),
        "content_type": classify_content_type(text, heading=section["title"]),
        "ceph_version": "9.9.1",
        "product": "IBM Storage Ceph"
    }

    return Chunk(
        text=embedded_text,
        metadata=metadata,
        token_count=estimate_tokens(embedded_text)
    )


def _split_oversized_chunks(
    chunks: List[Chunk],
    max_tokens: int,
    overlap_tokens: int
) -> List[Chunk]:
    """Split chunks exceeding max_tokens at paragraph boundaries with overlap."""
    result = []

    for chunk in chunks:
        if chunk.token_count <= max_tokens:
            result.append(chunk)
        else:
            # Split by paragraphs
            paragraphs = chunk.text.split('\n\n')
            current_text = ""
            current_tokens = 0

            for para in paragraphs:
                para_tokens = estimate_tokens(para)

                if current_tokens + para_tokens > max_tokens and current_text:
                    # Save current chunk
                    result.append(Chunk(
                        text=current_text,
                        metadata=chunk.metadata.copy(),
                        token_count=current_tokens
                    ))
                    # Start new chunk with overlap
                    overlap_text = _get_overlap_text(current_text, overlap_tokens)
                    current_text = overlap_text + "\n\n" + para if overlap_text else para
                    current_tokens = estimate_tokens(current_text)
                else:
                    current_text += "\n\n" + para if current_text else para
                    current_tokens += para_tokens

            if current_text:
                result.append(Chunk(
                    text=current_text,
                    metadata=chunk.metadata.copy(),
                    token_count=current_tokens
                ))

    return result


def _get_overlap_text(text: str, n_tokens: int) -> str:
    """Get last n tokens as overlap text."""
    tokens = get_encoder().encode(text)
    if len(tokens) <= n_tokens:
        return text
    overlap_token_ids = tokens[-n_tokens:]
    return get_encoder().decode(overlap_token_ids)


# ─── Batch Processing Helper ─────────────────────────────────────────────

def process_markdown_files(
    md_root: Path,
    max_tokens: int = 512,
    overlap_tokens: int = 50,
    min_chunk_tokens: int = 30
) -> List[Chunk]:
    """
    Process all markdown files in directory tree.

    Args:
        md_root: Root directory containing markdown files
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlap between split chunks
        min_chunk_tokens: Minimum tokens to keep a chunk

    Returns:
        List of all chunks from all files
    """
    md_files = list(md_root.rglob("*.md"))
    all_chunks = []

    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        rel_path = md_file.relative_to(md_root)
        chunks = chunk_markdown(
            text,
            str(rel_path),
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            min_chunk_tokens=min_chunk_tokens
        )
        all_chunks.extend(chunks)

    return all_chunks