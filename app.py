"""
app.py — Flask application for the IBM Ceph Documentation Scraper + RAG.

Routes:
  GET  /                        — Main UI (Excel-driven scraper)
  GET  /toc                     — TOC Scraper UI
  GET  /docs                    — Markdown file browser
  GET  /docs/<path:filename>    — GitHub-style markdown viewer
  GET  /api/excel-files         — List available TOC Excel files
  GET  /api/excel-info          — Get metadata for a selected Excel file
  POST /api/start               — Start a scrape job (returns job_id)
  GET  /api/status/<id>         — Poll job status + progress
  GET  /api/download/<id>       — Download zipped Markdown output
  POST /api/cancel/<id>         — Cancel a running job
  GET  /api/jobs                — List all scrape jobs
  POST /api/toc/scrape          — Start a TOC scrape job (returns job_id)
  GET  /api/toc/status/<id>     — Poll TOC job status + log
  GET  /api/toc/download/<id>   — Download the generated Excel file
  POST /api/toc/cancel/<id>     — Cancel a running TOC job
  GET  /rag                     — RAG UI
  POST /api/rag/ingest          — Start RAG ingestion job (returns job_id)
  GET  /api/rag/ingest/status/<id> — Poll ingestion job status
  POST /api/rag/query           — Query RAG (semantic search + LLM)
  POST /api/rag/search          — Semantic search only (no LLM)
"""

import sys
import io
import os
import re
import uuid
import zipfile
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Remove any user-level site-packages injected via PYTHONPATH that can shadow or
# break packages installed inside .venv (e.g. a system torchaudio missing torio).
_venv_site = os.path.join(sys.prefix, "Lib", "site-packages")
sys.path = [p for p in sys.path if os.path.abspath(p) == os.path.abspath(_venv_site)
            or not p.endswith("site-packages")
            or p.startswith(sys.prefix)]

# Ensure HuggingFace cache uses E: drive (must be set BEFORE importing transformers/sentence_transformers)
os.environ.setdefault("HF_HOME", "E:/hf-cache")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("OMP_NUM_THREADS", "4")

from flask import Flask, jsonify, request, send_file, render_template, abort, Response
import markdown as md_lib
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.toc import TocExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension

from core.excel_parser import parse_excel_toc, slugify
from core.scraper import scrape_all
from core.converter import html_to_markdown
from toc.toc_scraper import fetch_toc
from toc.toc_excel import write_toc_excel
# ── Setup logging first (before RAG imports) ──────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# RAG imports (after logger exists)
try:
    import yaml
    import chromadb
    from chromadb.utils import embedding_functions
    from rag_pipeline.chunker import process_markdown_files, Chunk
    from rag_pipeline.llm_client import get_llm_client, load_config as load_llm_config
    RAG_AVAILABLE = True
    logger.info("RAG dependencies loaded successfully")
except ImportError as e:
    logger.warning(f"RAG dependencies not available: {e}")
    RAG_AVAILABLE = False
    embedding_functions = None  # ensure name is always defined

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

OUTPUT_DIR         = Path("output")
OUTPUT_DIR_MD      = OUTPUT_DIR / "md"
OUTPUT_DIR_HTML    = OUTPUT_DIR / "html"
OUTPUT_DIR_XLS     = OUTPUT_DIR / "excel"
OUTPUT_DIR_CHROMA  = OUTPUT_DIR / "chroma_db"

for _d in (OUTPUT_DIR, OUTPUT_DIR_MD, OUTPUT_DIR_HTML, OUTPUT_DIR_XLS, OUTPUT_DIR_CHROMA):
    _d.mkdir(parents=True, exist_ok=True)

# ── In-memory job stores ───────────────────────────────────────────────────────
# Markdown scrape jobs
jobs: Dict[str, Dict[str, Any]] = {}
job_locks: Dict[str, threading.Event] = {}

# TOC scrape jobs
toc_jobs: Dict[str, Dict[str, Any]] = {}
toc_job_locks: Dict[str, threading.Event] = {}


# ── Background scrape worker ──────────────────────────────────────────────────

def check_md_file_needs_scrape(filepath: Path) -> bool:
    if not filepath.exists():
        return True
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return True
        
    if not content.strip():
        return True
        
    lines = [line.strip() for line in content.split("\n")]
    
    # Specific boilerplate lines to strip for content-emptiness checks
    boilerplate_exact_lines = {
        "change version", "9.9.1", "9.9.0", "8.1.0", "8.0.0", "7.1.0", "7.0.0", "6.1.0", "5.3.0",
        "was this topic helpful?", "focus sentinel", "close", "rate this content",
        "thank you for your feedback!", "together, we can continue to improve ibm documentation.",
        "return to topic", "thank you for your submission.", "submissions are limited to 1 per day per topic.",
        "error submitting rating", "there has been an error sending your feedback to the team. your comment was saved locally, if not in an incognito browser, and will be available when attempting to submit feedback again.",
        "please try again later.", "loading", "active loading indicator"
    }
    
    # Substring matches for boilerplate and system warnings
    boilerplate_substrings = [
        "focus sentinel", "was this topic helpful", "rate this content", "thank you for your feedback", 
        "together, we can continue to improve ibm documentation", "return to topic", "thank you for your submission", 
        "submissions are limited to 1 per day per topic", "error submitting rating", "there has been an error sending your feedback", 
        "please try again later", "change version", "active loading indicator", "loading", "close", 
        "get hands-on experience with ibm tech", "?lit$", "docs offline", "security update required for ibm docs offline", 
        "continue download", "visit the docs offline page", "view the security bulletin"
    ]
    
    real_lines = []
    for line in lines:
        cleaned_line = line.lstrip("#").strip()
        cleaned_lower = cleaned_line.lower()
        
        # Skip index, source header and footer lines
        if line.startswith("# ") or line.startswith("> **Index:**") or line.startswith("> **Source:**") or line == "---" or line.startswith("*Source:"):
            continue
        if not line:
            continue
        if cleaned_lower in boilerplate_exact_lines:
            continue
        if any(sub in cleaned_lower for sub in boilerplate_substrings):
            continue
            
        real_lines.append(line)
        
    real_content_len = len(" ".join(real_lines).strip())
    # If the remaining non-boilerplate text is less than 10 characters, it's a failed scrape
    return real_content_len < 10



def _run_scrape_job(job_id: str, excel_file: str, rate_limit: float, resume: bool = False, resume_session_dir: Optional[str] = None):
    """
    Runs in a background thread. Supports standard scraping or resuming failed pages in the same folder.
    """
    job          = jobs[job_id]
    cancel_event = job_locks[job_id]

    try:
        # ── Step 1: Parse Excel ───────────────────────────────────────────────
        job["log"].append(f"📂 Parsing Excel TOC: {excel_file}")
        excel_path = OUTPUT_DIR_XLS / excel_file
        toc = parse_excel_toc(excel_path)
        entries = toc["entries"]
        sections = toc["sections"]
        total = len(entries)
        # Category slug drives the output folder name (fallback to excel stem)
        category_slug = toc.get("category_slug", "") or Path(excel_file).stem

        if total == 0:
            job["status"] = "error"
            job["error"] = "No URLs found in the selected Excel file."
            return

        job["total"] = total
        job["log"].append(
            f"🔗 Found {total} URLs across {len(sections)} top-level sections."
        )

        # ── Step 2: Create or resolve session directory ──────────────────────
        if resume:
            if resume_session_dir:
                session_dir = OUTPUT_DIR_MD / resume_session_dir
            else:
                # Find latest directory matching category_slug
                matching_dirs = sorted(
                    [d for d in OUTPUT_DIR_MD.iterdir() if d.is_dir() and d.name == category_slug],
                    key=lambda d: d.name,
                    reverse=True
                )
                if matching_dirs:
                    session_dir = matching_dirs[0]
                else:
                    session_dir = OUTPUT_DIR_MD / category_slug
            session_dir.mkdir(parents=True, exist_ok=True)
            job["output_dir"] = session_dir.name
            job["log"].append(f"🔄 Resuming session folder: output/md/{session_dir.name}/")
        else:
            session_dir = OUTPUT_DIR_MD / category_slug
            session_dir.mkdir(parents=True, exist_ok=True)
            job["output_dir"] = session_dir.name
            job["log"].append(f"📁 Session folder: output/md/{session_dir.name}/")

        # ── Step 3: Pre-create one subfolder per top-level section ───────────
        section_dirs: Dict[str, Path] = {}
        for sec in sections:
            folder_name = f"{sec['index']}-{sec['slug']}"
            folder      = session_dir / folder_name
            folder.mkdir(exist_ok=True)
            section_dirs[sec["index"]] = folder

        # ── Build URL → entry lookup (for the on_result callback) ─────────────
        url_entry_map: Dict[str, Dict] = {e["url"]: e for e in entries}

        # ── Step 4: Scan and filter files to scrape if resuming ────────────────
        urls_to_scrape = []
        already_ok = 0

        for e in entries:
            ti     = e["top_index"]
            folder = section_dirs.get(ti, session_dir)
            file_slug = slugify(e["description"])
            filename  = f"{e['index']}-{file_slug}.md"
            filepath  = folder / filename

            if resume:
                if not check_md_file_needs_scrape(filepath):
                    already_ok += 1
                else:
                    urls_to_scrape.append(e["url"])
            else:
                urls_to_scrape.append(e["url"])

        if resume:
            job["log"].append(f"🔍 Scan complete: {already_ok} files are already successfully scraped.")
            job["log"].append(f"⚡ {len(urls_to_scrape)} failed/incomplete files need attention.")
            job["files_ok"] = already_ok
            job["files_created"] = already_ok
            job["progress"] = already_ok

        if not urls_to_scrape:
            job["status"] = "done"
            job["progress"] = total
            job["log"].append("🎉 All files are already successfully scraped! Nothing to do.")
            return

        urls = urls_to_scrape

        def on_result(url: str, content_html, i: int, total_scrapes: int):
            """Called by scrape_all() immediately after each page is fetched."""
            current_progress = already_ok + i if resume else i
            job["progress"]    = current_progress
            job["current_url"] = url

            entry = url_entry_map.get(url)
            if not entry:
                job["log"].append(f"[{current_progress}/{total}] ⚠️ No entry found for URL, skipping.")
                return

            ti     = entry["top_index"]
            folder = section_dirs.get(ti, session_dir)

            # File name: <index>-<slug>.md   e.g. 12.3.8-bootstrapping-a-new-storage-cluster.md
            file_slug = slugify(entry["description"])
            filename  = f"{entry['index']}-{file_slug}.md"
            filepath  = folder / filename

            if content_html:
                page_md = html_to_markdown(content_html, heading_depth_offset=1)

                # Build the full .md file content
                lines = [
                    f"# {entry['description']}",
                    "",
                    f"> **Index:** `{entry['index']}`  ",
                    f"> **Source:** [{url}]({url})",
                    "",
                    "---",
                    "",
                    page_md,
                    "",
                    "---",
                    "",
                    f"*Source: [{url}]({url})*",
                ]
                filepath.write_text("\n".join(lines), encoding="utf-8")

                job["files_created"] += 1
                job["files_ok"]      += 1
                job["log"].append(
                    f"[{current_progress}/{total}] ✅ {entry['index']} — {entry['description'][:55]}"
                )
            else:
                # Write a stub file so the entry is still in the output
                lines = [
                    f"# {entry['description']}",
                    "",
                    "> ⚠️ Content could not be fetched.",
                    "",
                    f"> **Index:** `{entry['index']}`  ",
                    f"> **Source:** [{url}]({url})",
                ]
                filepath.write_text("\n".join(lines), encoding="utf-8")

                job["files_created"] += 1
                job["files_failed"]  += 1
                job["log"].append(
                    f"[{current_progress}/{total}] ❌ {entry['index']} — {entry['description'][:55]}"
                )

        scrape_all(
            urls=urls,
            rate_limit_seconds=rate_limit,
            on_result=on_result,
            cancel_check=lambda: cancel_event.is_set(),
        )

        # ── Step 5: Finalise ──────────────────────────────────────────────────
        fc = job["files_created"]
        fk = job["files_ok"]
        ff = job["files_failed"]

        if cancel_event.is_set():
            job["status"] = "cancelled"
            job["log"].append(
                f"🛑 Cancelled — {fc} files saved ({fk} ok, {ff} failed)."
            )
        else:
            job["status"] = "done"
            job["log"].append(
                f"✅ Done!  {fk} files written, {ff} failed."
            )
            job["log"].append(
                f"📁 Output: output/md/{session_dir.name}/"
            )

    except Exception as exc:
        logger.exception(f"Job {job_id} failed with exception")
        job["status"] = "error"
        job["error"]  = str(exc)
        job["log"].append(f"💥 Error: {exc}")


# ── Scraper Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main scraper UI."""
    return render_template("index.html")


@app.route("/api/excel-files")
def api_excel_files():
    """List available TOC Excel files, newest first, with category metadata."""
    files = sorted(
        OUTPUT_DIR_XLS.glob("*.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    result = []
    for f in files:
        try:
            toc = parse_excel_toc(f)
            category_name = toc.get("category_name", "")
            category_slug = toc.get("category_slug", "")
        except Exception:
            category_name = ""
            category_slug = ""
        result.append({
            "name":          f.name,
            "mtime":         datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            "size":          f.stat().st_size,
            "category_name": category_name,
            "category_slug": category_slug,
        })
    return jsonify(result)


@app.route("/api/excel-info")
def api_excel_info():
    """Return metadata for a selected Excel file (total URLs + section list)."""
    filename = request.args.get("file", "").strip()
    if not filename:
        return jsonify({"error": "No file specified."}), 400

    path = OUTPUT_DIR_XLS / filename
    if not path.exists():
        return jsonify({"error": f"File not found: {filename}"}), 404

    try:
        toc = parse_excel_toc(path)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({
        "total":          toc["total"],
        "section_count":  len(toc["sections"]),
        "category_name":  toc.get("category_name", ""),
        "category_slug":  toc.get("category_slug", ""),
        "sections": [
            {
                "index":       s["index"],
                "description": s["description"],
                "entry_count": s["entry_count"],
            }
            for s in toc["sections"]
        ],
    })


@app.route("/api/detect-session/<excel_file>")
def api_detect_session(excel_file: str):
    """Detect if there is an existing session folder for the selected Excel file."""
    excel_file = excel_file.strip()
    if not excel_file:
        return jsonify({"session_dir": None})

    try:
        toc = parse_excel_toc(OUTPUT_DIR_XLS / excel_file)
        category_slug = toc.get("category_slug", "") or Path(excel_file).stem
    except Exception:
        category_slug = Path(excel_file).stem

    try:
        session_dir = OUTPUT_DIR_MD / category_slug
        if session_dir.is_dir():
            return jsonify({"session_dir": category_slug})
    except Exception as e:
        logger.warning(f"Error listing output directory: {e}")

    return jsonify({"session_dir": None})


@app.route("/api/scan-status", methods=["POST"])
def api_scan_status():
    """Perform a quick scan of the files on disk and return status."""
    data = request.get_json(silent=True) or {}
    excel_file = (data.get("excel_file") or "").strip()
    session_dir_name = (data.get("session_dir") or "").strip()

    if not excel_file:
        return jsonify({"error": "No Excel file selected."}), 400

    excel_path = OUTPUT_DIR_XLS / excel_file
    if not excel_path.exists():
        return jsonify({"error": "Excel file not found."}), 404

    if not session_dir_name:
        # Auto-detect from category slug
        try:
            toc_meta = parse_excel_toc(excel_path)
            session_dir_name = toc_meta.get("category_slug", "") or Path(excel_file).stem
        except Exception as e:
            return jsonify({"error": f"Error reading Excel: {e}"}), 500

        if not (OUTPUT_DIR_MD / session_dir_name).is_dir():
            return jsonify({
                "total": 0,
                "clean": 0,
                "failed": 0,
                "session_dir": None,
                "message": "No existing session found."
            })
            
    session_dir = OUTPUT_DIR_MD / session_dir_name
    if not session_dir.exists() or not session_dir.is_dir():
        return jsonify({"error": f"Session directory not found: {session_dir_name}"}), 404
        
    try:
        toc = parse_excel_toc(excel_path)
        entries = toc["entries"]
        sections = toc["sections"]
        
        section_map = {sec["index"]: sec["description"] for sec in sections}
        
        total = len(entries)
        clean = 0
        failed = 0
        
        for e in entries:
            ti = e["top_index"]
            sec_desc = section_map.get(ti)
            if not sec_desc:
                sec_folder_name = ti
            else:
                sec_folder_name = f"{ti}-{slugify(sec_desc)}"
                
            file_slug = slugify(e["description"])
            filename = f"{e['index']}-{file_slug}.md"
            filepath = session_dir / sec_folder_name / filename
            
            if check_md_file_needs_scrape(filepath):
                failed += 1
            else:
                clean += 1
                
        return jsonify({
            "total": total,
            "clean": clean,
            "failed": failed,
            "session_dir": session_dir_name
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/start", methods=["POST"])
def api_start():
    """Start a scrape job. Returns job_id. Supports optional resume of failed pages."""
    data       = request.get_json(silent=True) or {}
    excel_file = (data.get("excel_file") or "").strip()
    rate_limit = float(data.get("rate_limit", 2.0))
    rate_limit = max(1.0, min(rate_limit, 10.0))   # clamp 1–10s
    resume     = bool(data.get("resume", False))
    session_dir_name = data.get("session_dir")

    if not excel_file:
        return jsonify({"error": "No Excel file selected."}), 400

    excel_path = OUTPUT_DIR_XLS / excel_file
    if not excel_path.exists():
        return jsonify({"error": f"Excel file not found: {excel_file}"}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "id":            job_id,
        "status":        "running",
        "progress":      0,
        "total":         0,
        "current_url":   "",
        "log":           [],
        "files_created": 0,
        "files_ok":      0,
        "files_failed":  0,
        "output_dir":    None,
        "error":         None,
        "started_at":    datetime.now().isoformat(),
    }
    job_locks[job_id] = threading.Event()

    thread = threading.Thread(
        target=_run_scrape_job,
        kwargs={
            "job_id": job_id,
            "excel_file": excel_file,
            "rate_limit": rate_limit,
            "resume": resume,
            "resume_session_dir": session_dir_name,
        },
        daemon=True,
    )
    thread.start()

    logger.info(f"Started job {job_id} (excel={excel_file}, rate={rate_limit}s, resume={resume})")
    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def api_status(job_id: str):
    """Poll job status and progress."""
    job = jobs.get(job_id)
    if not job:
        abort(404)

    return jsonify({
        "id":            job["id"],
        "status":        job["status"],
        "progress":      job["progress"],
        "total":         job["total"],
        "current_url":   job["current_url"],
        "log":           job["log"][-50:],          # last 50 lines
        "files_created": job.get("files_created", 0),
        "files_ok":      job.get("files_ok", 0),
        "files_failed":  job.get("files_failed", 0),
        "output_dir":    job.get("output_dir"),
        "error":         job["error"],
        "started_at":    job["started_at"],
    })


@app.route("/api/download/<job_id>")
def api_download(job_id: str):
    """Stream a zip of all Markdown files from the session folder."""
    job = jobs.get(job_id)
    if not job or not job.get("output_dir"):
        abort(404)

    session_dir = OUTPUT_DIR_MD / job["output_dir"]
    if not session_dir.exists():
        abort(404)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for md_file in sorted(session_dir.rglob("*.md")):
            zf.write(md_file, md_file.relative_to(session_dir))
    buf.seek(0)

    prefix   = "PARTIAL-" if job["status"] == "running" else ""
    zip_name = f"{prefix}{job['output_dir']}.zip"

    return send_file(
        buf,
        as_attachment=True,
        download_name=zip_name,
        mimetype="application/zip",
    )


@app.route("/api/cancel/<job_id>", methods=["POST"])
def api_cancel(job_id: str):
    """Request cancellation of a running job."""
    job = jobs.get(job_id)
    if not job:
        abort(404)
    event = job_locks.get(job_id)
    if event:
        event.set()
    return jsonify({"ok": True})


@app.route("/api/jobs")
def api_jobs():
    """List all scrape jobs (most recent first)."""
    result = []
    for job in sorted(jobs.values(), key=lambda j: j["started_at"], reverse=True):
        result.append({
            "id":            job["id"],
            "status":        job["status"],
            "progress":      job["progress"],
            "total":         job["total"],
            "files_created": job.get("files_created", 0),
            "output_dir":    job.get("output_dir"),
            "started_at":    job["started_at"],
        })
    return jsonify(result)


# ── Docs viewer ───────────────────────────────────────────────────────────────

def _md_files():
    """
    Return list of .md files in OUTPUT_DIR_MD (all subdirs), newest first.

    Returns dicts with keys: path (relative), name, folder, size, mtime.
    """
    files = sorted(
        OUTPUT_DIR_MD.rglob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    result = []
    for f in files:
        if f.name == ".gitkeep":
            continue
        stat = f.stat()
        rel  = f.relative_to(OUTPUT_DIR_MD)
        result.append({
            "path":   str(rel).replace("\\", "/"),
            "name":   f.name,
            "folder": rel.parent.name if rel.parent != Path(".") else "",
            "size":   stat.st_size,
            "mtime":  datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return result


def _render_md(text: str):
    """Convert markdown text to HTML with TOC, tables, fenced code, syntax highlight."""
    # Strip "Copy to clipboard" noise that IBM docs pages sometimes contain
    text = "\n".join(
        line for line in text.splitlines()
        if line.strip() != "Copy to clipboard"
    )
    extensions = [
        FencedCodeExtension(),
        TableExtension(),
        TocExtension(permalink=True, toc_depth="2-5"),
        CodeHiliteExtension(linenums=False, css_class="highlight"),
        "nl2br",
        "sane_lists",
        "attr_list",
        "def_list",
        "footnotes",
    ]
    mdobj = md_lib.Markdown(extensions=extensions)
    html  = mdobj.convert(text)
    toc   = mdobj.toc
    return html, toc


@app.route("/docs")
def docs_index():
    """List all markdown output files grouped by section folder."""
    files = _md_files()
    # Group by folder for the template
    groups: Dict[str, list] = {}
    for f in files:
        folder = f["folder"] or "_root"
        groups.setdefault(folder, []).append(f)
    return render_template("docs.html", files=files, groups=groups)


@app.route("/docs/raw/<path:filename>")
def docs_raw(filename: str):
    """Serve a raw markdown file as a download."""
    target = (OUTPUT_DIR_MD / filename).resolve()
    if not str(target).startswith(str(OUTPUT_DIR_MD.resolve())):
        abort(403)
    if not target.exists() or target.suffix != ".md":
        abort(404)
    return send_file(
        str(target),
        as_attachment=True,
        download_name=filename.replace("/", "-"),
        mimetype="text/markdown",
    )


@app.route("/docs/<path:filename>")
def docs_view(filename: str):
    """Render a single markdown file as a GitHub-style page."""
    target = (OUTPUT_DIR_MD / filename).resolve()
    if not str(target).startswith(str(OUTPUT_DIR_MD.resolve())):
        abort(403)
    if not target.exists() or target.suffix != ".md":
        abort(404)

    raw              = target.read_text(encoding="utf-8")
    html_body, toc_html = _render_md(raw)
    file_size        = target.stat().st_size
    file_mtime       = datetime.fromtimestamp(target.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    line_count       = raw.count("\n")

    return render_template(
        "viewer.html",
        filename=filename,
        html_body=html_body,
        toc_html=toc_html,
        file_size=file_size,
        file_mtime=file_mtime,
        line_count=line_count,
    )


# ── TOC background worker ─────────────────────────────────────────────────────

def _run_toc_job(job_id: str, url: str, category_name: str = ""):
    """
    Runs in a background thread.
    1. Uses fetch_toc() to open a browser, expand the full sidebar, build indices.
    2. Writes results to a styled .xlsx file named after the category.
    3. Stores entries + skipped list on the job dict.
    """
    job = toc_jobs[job_id]
    cancel_event = toc_job_locks[job_id]

    def on_log(msg: str):
        job["log"].append(msg)

    try:
        job["log"].append(f"🚀 Starting TOC scrape for: {url}")
        if category_name:
            job["log"].append(f"🏷️  Category: {category_name}")

        if cancel_event.is_set():
            job["status"] = "cancelled"
            return

        # fetch_toc now returns {"entries": [...], "skipped": [...]}
        result  = fetch_toc(url, on_log=on_log)
        entries = result["entries"]
        skipped = result["skipped"]

        if cancel_event.is_set():
            job["status"] = "cancelled"
            job["log"].append("🛑 Cancelled.")
            return

        if not entries:
            job["status"] = "error"
            job["error"] = "No TOC links were found on the page."
            return

        # Write Excel file — named after category slug if available
        cat_slug    = slugify(category_name) if category_name else "toc"
        output_file = OUTPUT_DIR_XLS / f"{cat_slug}.xlsx"
        write_toc_excel(entries, output_file, skipped=skipped, category_name=category_name)

        top_level = sum(1 for e in entries if "." not in e["index"])

        job["status"]          = "done"
        job["output_file"]     = str(output_file)
        job["output_filename"] = output_file.name
        job["total_entries"]   = len(entries)
        job["top_level"]       = top_level
        job["entries"]         = entries   # for UI preview table
        job["skipped"]         = skipped   # sections that failed all retries

        job["log"].append(
            f"📊 {len(entries)} entries  |  {top_level} top-level  |  "
            f"{len(skipped)} section(s) skipped"
        )
        if skipped:
            job["log"].append("⚠️  Skipped sections (investigate these):")
            for s in skipped:
                job["log"].append(
                    f"    • {s['description']!r}  key={s['key']}  reason={s['reason']}"
                )
        job["log"].append(f"💾 Saved: {output_file.name}")
        job["log"].append("✅ Done!")

    except Exception as exc:
        logger.exception(f"TOC job {job_id} failed")
        job["status"] = "error"
        job["error"] = str(exc)
        job["log"].append(f"💥 Error: {exc}")


# ── RAG Background Workers ────────────────────────────────────────────────────

rag_jobs: Dict[str, Dict[str, Any]] = {}
rag_job_locks: Dict[str, threading.Event] = {}

# Global RAG components (lazy-loaded, keyed by category_slug)
_rag_embedding_fn: Dict[str, Any] = {}
_rag_collection:   Dict[str, Any] = {}
_rag_llm_client:   Dict[str, Any] = {}
_rag_base_config = None   # base config loaded once from config.yaml


def _load_rag_base_config(force_reload: bool = False) -> dict:
    """Load base RAG configuration (provider/model settings only)."""
    global _rag_base_config
    if _rag_base_config is None or force_reload:
        config_path = Path("rag_pipeline/config.yaml")
        with open(config_path, "r") as f:
            _rag_base_config = yaml.safe_load(f)
    return _rag_base_config


def _build_category_config(category_slug: str) -> dict:
    """Build a per-category config by overlaying paths derived from the slug
    onto the shared base config from config.yaml.

    Paths:
      md_root      → output/md/<slug>
      chroma_db    → output/chroma_db/<slug>
      collection   → <slug>  (ChromaDB collection name)

    The system prompts are left generic when no override is found.
    """
    base = _load_rag_base_config()
    import copy
    cfg = copy.deepcopy(base)
    cfg["paths"] = {
        "md_root":         str(OUTPUT_DIR_MD / category_slug),
        "chroma_db":       str(OUTPUT_DIR_CHROMA / category_slug),
        "collection_name": category_slug,
    }
    # Replace product-specific wording in system prompts with the category label
    display_name = category_slug.replace("-", " ").title()
    for key in ("system", "system_low_confidence"):
        orig = cfg.get("prompt", {}).get(key, "")
        if "IBM Storage Ceph" in orig:
            cfg["prompt"][key] = orig.replace("IBM Storage Ceph 9.9.1", display_name).replace("IBM Storage Ceph", display_name)
    return cfg


def _load_rag_config(category_slug: str = "", force_reload: bool = False) -> dict:
    """Return the effective config for a given category slug.

    If no slug is given, falls back to the base config (legacy behaviour).
    """
    if not category_slug:
        return _load_rag_base_config(force_reload)
    return _build_category_config(category_slug)


def _make_ollama_embedding_fn(emb_config: dict):
    """Build a ChromaDB-compatible embedding function backed by Ollama."""
    if not RAG_AVAILABLE:
        raise RuntimeError("RAG dependencies not available.")
    import ollama as _ollama

    model = emb_config["model"]
    base_url = emb_config.get("base_url", "http://localhost:11434")
    batch_size = emb_config.get("batch_size", 64)
    client = _ollama.Client(host=base_url)

    class OllamaEmbeddingFunction(embedding_functions.EmbeddingFunction):
        def __init__(self):
            pass

        def __call__(self, texts):
            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                resp = client.embed(model=model, input=batch)
                all_embeddings.extend(resp["embeddings"])
            return all_embeddings

    return OllamaEmbeddingFunction()


def _get_rag_embedding_fn(category_slug: str = ""):
    """Lazy-load embedding function (shared across categories — same model)."""
    global _rag_embedding_fn
    key = category_slug or "__default__"
    if key not in _rag_embedding_fn:
        config = _load_rag_config(category_slug)
        emb_config = config["embeddings"]
        _rag_embedding_fn[key] = _make_ollama_embedding_fn(emb_config)
    return _rag_embedding_fn[key]


def _get_rag_collection(category_slug: str = ""):
    """Lazy-load ChromaDB collection for the given category.

    Always validates the cached handle is still alive by peeking at it.
    If ChromaDB raises (collection deleted/replaced since last ingest),
    the stale handle is dropped and a fresh one is fetched.
    """
    global _rag_collection
    key = category_slug or "__default__"

    if key in _rag_collection:
        try:
            _rag_collection[key].count()  # lightweight liveness check
        except Exception:
            del _rag_collection[key]  # stale — force re-fetch below

    if key not in _rag_collection:
        config = _load_rag_config(category_slug)
        embedding_fn = _get_rag_embedding_fn(category_slug)
        db_path = config["paths"]["chroma_db"]
        Path(db_path).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=db_path)
        try:
            _rag_collection[key] = client.get_collection(
                name=config["paths"]["collection_name"],
                embedding_function=embedding_fn
            )
        except Exception:
            raise RuntimeError(
                f"RAG collection for '{category_slug or 'default'}' not found. "
                "Please run Ingestion first (RAG tab → Ingestion → Start Ingestion)."
            )
    return _rag_collection[key]


def _get_rag_llm_client(category_slug: str = ""):
    """Lazy-load LLM client (shared model, per-category config)."""
    global _rag_llm_client
    key = category_slug or "__default__"
    if key not in _rag_llm_client:
        config = _load_rag_config(category_slug)
        _rag_llm_client[key] = get_llm_client(config)
    return _rag_llm_client[key]


def _run_rag_ingest_job(job_id: str, category_slug: str = ""):
    """Background RAG ingestion job for the given category."""
    job = rag_jobs[job_id]
    cancel_event = rag_job_locks[job_id]

    def on_log(msg: str):
        job["log"].append(msg)

    try:
        job["log"].append("🚀 Starting RAG ingestion...")
        config = _load_rag_config(category_slug)

        if category_slug:
            job["log"].append(f"🏷️  Category: {category_slug}")

        # Create Ollama embedding function
        emb_config = config["embeddings"]
        job["log"].append(f"📦 Connecting to Ollama embedding model ({emb_config['model']})...")
        embedding_fn = _make_ollama_embedding_fn(emb_config)
        job["log"].append("✅ Embedding function ready")

        # Create ChromaDB collection (drop & recreate to ensure clean state)
        job["log"].append("🗄️  Connecting to ChromaDB...")
        db_path = config["paths"]["chroma_db"]
        Path(db_path).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=db_path)
        collection_name = config["paths"]["collection_name"]
        try:
            client.delete_collection(collection_name)
            job["log"].append("🗑️  Cleared existing collection")
        except Exception:
            pass  # Collection didn't exist yet — that's fine
        collection = client.create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
            metadata={
                "hnsw:space": config["vectordb"].get("hnsw_space", "cosine"),
                "hnsw:construction_ef": config["vectordb"].get("hnsw_construction_ef", 200),
                "hnsw:M": config["vectordb"].get("hnsw_M", 16)
            }
        )
        job["log"].append(f"✅ ChromaDB ready  →  output/chroma_db/{collection_name}/")

        # Process markdown files
        job["log"].append("✂️  Chunking documents...")
        chunk_config = config["chunking"]
        md_root = Path(config["paths"]["md_root"])

        if not md_root.exists():
            job["status"] = "error"
            job["error"] = f"Markdown root not found: {md_root}"
            job["log"].append(f"❌ {job['error']}")
            return

        chunks = process_markdown_files(
            md_root,
            max_tokens=chunk_config["max_tokens"],
            overlap_tokens=chunk_config["overlap_tokens"],
            min_chunk_tokens=chunk_config["min_chunk_tokens"]
        )
        job["log"].append(f"✅ Created {len(chunks)} chunks")

        # Ingest into ChromaDB in small batches to avoid Windows socket exhaustion
        import time
        job["log"].append(f"💾 Ingesting {len(chunks)} chunks...")
        batch_size = 16
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        for i in range(0, len(chunks), batch_size):
            if cancel_event.is_set():
                job["status"] = "cancelled"
                job["log"].append("🛑 Cancelled")
                return
            batch = chunks[i:i + batch_size]
            ids = [f"chunk_{i + j}" for j in range(len(batch))]
            documents = [c.text for c in batch]
            metadatas = [c.metadata for c in batch]
            collection.add(ids=ids, documents=documents, metadatas=metadatas)
            batch_num = i // batch_size + 1
            if batch_num % 10 == 0 or batch_num == total_batches:
                job["log"].append(f"   ⏳ {batch_num}/{total_batches} batches ({i + len(batch)}/{len(chunks)} chunks)")
            time.sleep(0.05)  # brief pause to let Windows reclaim TCP ports between batches

        # Invalidate the cached collection handle so the next query
        # fetches the freshly-created collection (new UUID).
        global _rag_collection
        key = category_slug or "__default__"
        if key in _rag_collection:
            del _rag_collection[key]

        # Statistics
        total_tokens = sum(c.token_count for c in chunks)
        job["status"] = "done"
        job["chunks_created"] = len(chunks)
        job["total_tokens"] = total_tokens
        job["log"].append(f"✅ Ingestion complete!")
        job["log"].append(f"   Chunks: {len(chunks)}")
        job["log"].append(f"   Tokens: {total_tokens:,}")

    except Exception as exc:
        logger.exception(f"RAG ingest job {job_id} failed")
        job["status"] = "error"
        job["error"] = str(exc)
        job["log"].append(f"💥 Error: {exc}")


def _rag_search(
    query: str,
    top_k: int = 5,
    chapter_filter: str = None,
    content_type_filter: str = None,
    topic_tags: List[str] = None,
    category_slug: str = ""
) -> List[Dict[str, Any]]:
    """Execute vector search against the given category collection."""
    collection = _get_rag_collection(category_slug)
    
    where = {}
    if chapter_filter:
        where["chapter"] = chapter_filter
    if content_type_filter:
        where["content_type"] = content_type_filter
    if topic_tags:
        where["topic_tags"] = {"$in": topic_tags}

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where if where else None,
        include=["documents", "metadatas", "distances"]
    )

    formatted = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        formatted.append({
            "text": doc,
            "metadata": meta,
            "score": 1 - dist,
            "distance": dist
        })

    return formatted


def _rewrite_query(question: str, llm_client) -> str:
    """Rewrite a conversational question into a concise search query for better retrieval.

    The goal is to strip conversational framing and surface the core technical
    keywords exactly as they appear in the documentation — without inventing
    chapter or domain terms that are not present in the question itself.
    """
    try:
        system = (
            "You are a search query optimizer for IBM Storage Ceph documentation. "
            "Your only job: rewrite the user question as 3-8 technical keywords "
            "that are most likely to appear verbatim in the matching documentation section. "
            "Rules:\n"
            "- Output ONLY the keywords, nothing else — no explanation, no punctuation, no quotes.\n"
            "- Do NOT add words that are not implied by the question (e.g. do NOT add 'installation', "
            "'disconnected', 'air gap', 'upgrade' unless the question mentions them).\n"
            "- Preserve exact Ceph object/daemon names (pool, osd, crush, rbd, rgw, cephfs, pg, mds, mgr).\n"
            "- For 'how to create X': output 'creating X' — use the gerund (e.g. 'creating osd', 'creating pool').\n"
            "- For 'how to add X' or 'how to deploy X': output 'adding X' or 'deploying X' — use the gerund.\n"
            "- For 'how to configure/enable/set X': output 'configuring X' or 'enabling X'.\n"
            "- For 'what is X' questions, output the full expanded name of X as used in Ceph docs:\n"
            "    'what is OSD' -> 'Ceph OSD Object Storage Daemon'\n"
            "    'what is MON' or 'what is monitor' -> 'Ceph Monitor daemon'\n"
            "    'what is MGR' or 'what is manager' -> 'Ceph Manager daemon'\n"
            "    'what is MDS' -> 'Ceph Metadata Server MDS'\n"
            "    'what is RGW' or 'what is object gateway' -> 'Ceph Object Gateway RGW'\n"
            "    'what is CRUSH' -> 'CRUSH Controlled Replication Under Scalable Hashing'\n"
            "    'what is BlueStore' -> 'BlueStore back-end object store'\n"
            "    'what is RBD' or 'what is block device' -> 'Ceph Block Device RBD'\n"
            "    'what is CephFS' or 'what is ceph filesystem' -> 'Ceph File System CephFS'\n"
            "    'what is PG' or 'what is placement group' -> 'placement group PG'\n"
            "    'what is RADOS' -> 'RADOS Reliable Autonomic Distributed Object Store'\n"
            "    For any other 'what is X': output 'X' followed by its common synonym or expansion.\n"
            "- For 'why is X' or 'X stuck/degraded/slow': output 'X state cause' or 'troubleshooting X'.\n"
            "- For questions about Kubernetes/OpenShift/containers with Ceph: output 'rbd kubernetes persistent volume' or similar.\n"
            "- Keep it short and precise — 3 to 8 words maximum."
        )
        prompt = f"Question: {question}\n\nKeywords:"
        rewritten = llm_client.generate(prompt, system).strip().strip('"').strip("'")
        # Sanity check: must be shorter than the original and not empty
        if not rewritten or len(rewritten) > 120 or len(rewritten) >= len(question) * 1.5:
            return question
        logger.info(f"Query rewritten: '{question}' -> '{rewritten}'")
        return rewritten
    except Exception:
        return question


def _extract_source_url(text: str) -> Optional[str]:
    """Extract the IBM docs URL embedded in a chunk's markdown footer."""
    m = re.search(r'\*Source:\s*\[.*?\]\((https?://[^)]+)\)', text)
    return m.group(1) if m else None


def _extract_snippet(text: str, max_chars: int = 220) -> str:
    """Return a clean plain-text preview of a chunk, stripping markdown syntax."""
    cleaned = re.sub(r'^>\s*\*\*(?:Index|Source):\*\*.*$', '', text, flags=re.MULTILINE)
    cleaned = re.sub(r'\*Source:.*', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'^#+\s*', '', cleaned, flags=re.MULTILINE)        # headings
    cleaned = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', cleaned)          # bold/italic
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)                       # inline code
    cleaned = re.sub(r'```.*?```', '', cleaned, flags=re.DOTALL)         # fenced code
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)          # links
    cleaned = re.sub(r'^\s*[-*>|:]+\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:max_chars] + ('…' if len(cleaned) > max_chars else '')


def _reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    k: int = 60
) -> List[Dict[str, Any]]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF score = sum(1 / (k + rank)) across all lists.
    Deduplication is by source_file + heading_path.
    """
    scores: Dict[str, float] = {}
    items: Dict[str, Dict[str, Any]] = {}

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            key = (
                chunk["metadata"].get("source_file", ""),
                chunk["metadata"].get("heading_path", "")
            )
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            # Keep the version with the highest original score for display
            if key not in items or chunk["score"] > items[key]["score"]:
                items[key] = chunk

    merged = sorted(items.values(), key=lambda c: scores[(
        c["metadata"].get("source_file", ""),
        c["metadata"].get("heading_path", "")
    )], reverse=True)
    return merged


def _rag_answer(
    question: str,
    top_k: int = 5,
    chapter_filter: str = None,
    content_type_filter: str = None,
    topic_tags: List[str] = None,
    show_sources: bool = True,
    category_slug: str = ""
) -> Dict[str, Any]:
    """Full RAG pipeline: retrieve + generate.

    Retrieval strategy:
    1. Rewrite the question into tight technical keywords.
    2. Search with both the rewritten query AND the original question.
    3. Merge results via Reciprocal Rank Fusion (RRF) to get the best of both.
    4. Drop chunks below the configured min_score threshold.
    5. If the best remaining chunk is below low_confidence_threshold, use the
       stricter low-confidence system prompt so the LLM won't hallucinate.
    6. Keep the top_k survivors for context.
    """
    config = _load_rag_config(category_slug)
    llm_client = _get_rag_llm_client(category_slug)
    retrieval_cfg = config.get("retrieval", {})
    min_score: float = retrieval_cfg.get("min_score", 0.0)
    low_confidence_threshold: float = retrieval_cfg.get("low_confidence_threshold", 0.72)

    # 1. Rewrite query into tight technical keywords
    search_query = _rewrite_query(question, llm_client)

    # 2. Fetch a wider candidate set from both query variants
    fetch_k = max(top_k * 3, 15)  # cast a wide net before filtering
    results_rewritten = _rag_search(
        search_query,
        top_k=fetch_k,
        chapter_filter=chapter_filter,
        content_type_filter=content_type_filter,
        topic_tags=topic_tags,
        category_slug=category_slug
    )
    # Only run the second search if the rewrite actually changed the query
    if search_query.strip().lower() != question.strip().lower():
        results_original = _rag_search(
            question,
            top_k=fetch_k,
            chapter_filter=chapter_filter,
            content_type_filter=content_type_filter,
            topic_tags=topic_tags,
            category_slug=category_slug
        )
        # 3. Merge with RRF
        chunks = _reciprocal_rank_fusion([results_rewritten, results_original])
    else:
        chunks = results_rewritten

    # 4. Drop chunks below minimum score threshold
    if min_score > 0.0:
        chunks = [c for c in chunks if c["score"] >= min_score]

    # 5. Keep top_k
    chunks = chunks[:top_k]

    if not chunks:
        return {
            "answer": "No relevant documentation found for this query.",
            "sources": [],
            "chunks_retrieved": 0,
            "search_query": search_query,
        }

    # Determine if the best chunk meets confidence expectations
    best_score = max(c["score"] for c in chunks)
    low_confidence = best_score < low_confidence_threshold

    # Re-sort: procedure chunks first, then others — scores within each group
    # are preserved so the LLM sees the most actionable content at the top.
    # This fixes cases where a concept/dashboard chunk outscores the CLI
    # procedure chunk by a small margin (e.g. CephFS create).
    CONTENT_TYPE_ORDER = {"procedure": 0, "reference": 1, "concept": 2, "troubleshooting": 3}
    chunks = sorted(
        chunks,
        key=lambda c: (
            CONTENT_TYPE_ORDER.get(c["metadata"].get("content_type", "concept"), 2),
            -c["score"]   # within same type, highest score first
        )
    )

    # Build context
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        source = meta.get("source_file", "unknown")
        section = meta.get("heading_path", "unknown")
        text = chunk["text"]
        context_parts.append(f"[Source {i}: {source} | {section}]\n{text}")
    context = "\n\n---\n\n".join(context_parts)

    # Build prompt — use stricter system prompt when confidence is low
    prompt_config = config.get("prompt", {})
    if low_confidence:
        system = prompt_config.get(
            "system_low_confidence",
            prompt_config.get("system", "You are an expert. Answer using the provided context.")
        )
    else:
        system = prompt_config.get("system", "You are an expert. Answer using the provided context.")
    template = prompt_config.get("template", "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:")
    prompt = template.format(context=context, question=question)

    # Generate answer
    answer = llm_client.generate(prompt, system)

    md_root_name = Path(config["paths"]["md_root"]).name

    return {
        "answer": answer,
        "search_query": search_query,
        "low_confidence": low_confidence,
        "best_score": round(best_score, 3),
        "md_root": md_root_name,
        "sources": [
            {
                "file": c["metadata"].get("source_file"),
                "section": c["metadata"].get("heading_path"),
                "chapter": c["metadata"].get("chapter"),
                "content_type": c["metadata"].get("content_type"),
                "score": c["score"],
                "snippet": _extract_snippet(c["text"]),
                "source_url": _extract_source_url(c["text"]),
            }
            for c in chunks
        ],
        "chunks_retrieved": len(chunks)
    }


# ── TOC Routes ────────────────────────────────────────────────────────────────

@app.route("/toc-index")
def toc_index_md():
    """Serve the generated IBM Ceph TOC markdown as a rendered doc page."""
    md_file = OUTPUT_DIR / "IBM-Ceph-TOC.md"
    if not md_file.exists():
        abort(404, "TOC markdown not yet generated. Run: node build_toc_md.mjs")
    raw = md_file.read_text(encoding="utf-8")
    html_body, toc_html = _render_md(raw)
    return render_template(
        "viewer.html",
        filename="IBM-Ceph-TOC.md",
        html_body=html_body,
        toc_html=toc_html,
        file_size=md_file.stat().st_size,
        file_mtime=datetime.fromtimestamp(md_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        line_count=raw.count("\n"),
    )


@app.route("/toc")
def toc_page():
    """Serve the TOC Scraper UI."""
    return render_template("toc.html")


@app.route("/api/toc/scrape", methods=["POST"])
def api_toc_scrape():
    """Start a TOC scrape job. Returns job_id."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    category_name = (data.get("category_name") or "").strip()

    if not url or not url.startswith("http"):
        return jsonify({"error": "A valid http(s) URL is required."}), 400
    if not category_name:
        return jsonify({"error": "A category name is required (e.g. 'IBM Storage Ceph 9.9.1')."}), 400

    job_id = str(uuid.uuid4())[:8]
    toc_jobs[job_id] = {
        "id": job_id,
        "status": "running",
        "log": [],
        "output_file": None,
        "output_filename": None,
        "category_name": category_name,
        "total_entries": 0,
        "top_level": 0,
        "entries": [],
        "skipped": [],
        "error": None,
        "started_at": datetime.now().isoformat(),
    }
    toc_job_locks[job_id] = threading.Event()

    thread = threading.Thread(
        target=_run_toc_job,
        args=(job_id, url, category_name),
        daemon=True,
    )
    thread.start()

    logger.info(f"Started TOC job {job_id} for {url} (category={category_name})")
    return jsonify({"job_id": job_id})


@app.route("/api/toc/status/<job_id>")
def api_toc_status(job_id: str):
    """Poll TOC job status, log lines, and results."""
    job = toc_jobs.get(job_id)
    if not job:
        abort(404)

    # Drain the log so the client only gets new lines on each poll
    log_snapshot = job["log"][:]
    job["log"] = []   # clear; client accumulates on its side

    return jsonify({
        "id": job["id"],
        "status": job["status"],
        "log": log_snapshot,
        "output_filename": job["output_filename"],
        "total_entries": job["total_entries"],
        "top_level": job["top_level"],
        "entries": job["entries"] if job["status"] == "done" else [],
        "skipped": job.get("skipped", []),
        "filename": job["output_filename"],
        "error": job["error"],
        "started_at": job["started_at"],
    })


@app.route("/api/toc/download/<job_id>")
def api_toc_download(job_id: str):
    """Download the generated Excel file."""
    job = toc_jobs.get(job_id)
    if not job:
        abort(404)
    if not job["output_file"]:
        abort(400)

    path = Path(job["output_file"])
    if not path.exists():
        abort(404)

    return send_file(
        str(path.resolve()),
        as_attachment=True,
        download_name=job["output_filename"],
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/api/toc/cancel/<job_id>", methods=["POST"])
def api_toc_cancel(job_id: str):
    """Request cancellation of a running TOC job."""
    job = toc_jobs.get(job_id)
    if not job:
        abort(404)
    event = toc_job_locks.get(job_id)
    if event:
        event.set()
    return jsonify({"ok": True})


# ── RAG Routes ────────────────────────────────────────────────────────────────

@app.route("/api/categories")
def api_categories():
    """Return all available categories.

    A category is available if it has a slugged Excel file in output/excel/
    with a valid category_name stored in the Info sheet.
    Each entry includes an 'ingested' flag indicating whether a ChromaDB
    collection folder already exists for that slug.
    """
    result = []
    seen_slugs = set()

    for excel_path in sorted(OUTPUT_DIR_XLS.glob("*.xlsx")):
        try:
            toc = parse_excel_toc(excel_path)
            category_name = toc.get("category_name", "").strip()
            category_slug = toc.get("category_slug", "").strip()
        except Exception:
            continue

        # Only list files that have a proper category_name embedded
        if not category_name or not category_slug:
            continue
        if category_slug in seen_slugs:
            continue
        seen_slugs.add(category_slug)

        ingested = (OUTPUT_DIR_CHROMA / category_slug).is_dir()
        md_ready  = (OUTPUT_DIR_MD / category_slug).is_dir()

        result.append({
            "slug":          category_slug,
            "label":         category_name,
            "ingested":      ingested,
            "md_ready":      md_ready,
            "excel_file":    excel_path.name,
        })

    # Sort: ingested first, then alphabetically
    result.sort(key=lambda c: (0 if c["ingested"] else 1, c["label"].lower()))
    return jsonify(result)


@app.route("/rag")
def rag_page():
    """Serve the RAG UI."""
    if not RAG_AVAILABLE:
        return "RAG dependencies not installed. Run: pip install -r rag-pipeline/requirements.txt", 503
    return render_template("rag.html")


@app.route("/api/rag/ingest", methods=["POST"])
def api_rag_ingest():
    """Start RAG ingestion job for a given category. Returns job_id."""
    if not RAG_AVAILABLE:
        return jsonify({"error": "RAG dependencies not available"}), 503

    data = request.get_json(silent=True) or {}
    category_slug = (data.get("category") or "").strip()
    if not category_slug:
        return jsonify({"error": "A category slug is required."}), 400

    job_id = str(uuid.uuid4())[:8]
    rag_jobs[job_id] = {
        "id": job_id,
        "status": "running",
        "category": category_slug,
        "log": [],
        "chunks_created": 0,
        "total_tokens": 0,
        "error": None,
        "started_at": datetime.now().isoformat(),
    }
    rag_job_locks[job_id] = threading.Event()

    thread = threading.Thread(
        target=_run_rag_ingest_job,
        args=(job_id, category_slug),
        daemon=True,
    )
    thread.start()

    logger.info(f"Started RAG ingest job {job_id} (category={category_slug})")
    return jsonify({"job_id": job_id})


@app.route("/api/rag/ingest/status/<job_id>")
def api_rag_ingest_status(job_id: str):
    """Poll RAG ingestion job status."""
    if not RAG_AVAILABLE:
        return jsonify({"error": "RAG dependencies not available"}), 503

    job = rag_jobs.get(job_id)
    if not job:
        abort(404)

    log_snapshot = job["log"][:]
    job["log"] = []

    return jsonify({
        "id": job["id"],
        "status": job["status"],
        "category": job.get("category", ""),
        "log": log_snapshot,
        "chunks_created": job.get("chunks_created", 0),
        "total_tokens": job.get("total_tokens", 0),
        "error": job["error"],
        "started_at": job["started_at"],
    })


@app.route("/api/rag/ingest/cancel/<job_id>", methods=["POST"])
def api_rag_ingest_cancel(job_id: str):
    """Cancel RAG ingestion job."""
    if not RAG_AVAILABLE:
        return jsonify({"error": "RAG dependencies not available"}), 503

    job = rag_jobs.get(job_id)
    if not job:
        abort(404)
    event = rag_job_locks.get(job_id)
    if event:
        event.set()
    return jsonify({"ok": True})


@app.route("/api/rag/search", methods=["POST"])
def api_rag_search():
    """Semantic search only (no LLM)."""
    if not RAG_AVAILABLE:
        return jsonify({"error": "RAG dependencies not available"}), 503

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    top_k = data.get("top_k", 5)
    chapter_filter = data.get("chapter_filter")
    content_type_filter = data.get("content_type_filter")
    topic_tags = data.get("topic_tags")
    category_slug = (data.get("category") or "").strip()

    if not query:
        return jsonify({"error": "Query is required"}), 400
    if not category_slug:
        return jsonify({"error": "A category is required."}), 400

    try:
        results = _rag_search(
            query,
            top_k=top_k,
            chapter_filter=chapter_filter,
            content_type_filter=content_type_filter,
            topic_tags=topic_tags,
            category_slug=category_slug
        )

        formatted = []
        for r in results:
            formatted.append({
                "text": r["text"][:500] + ("..." if len(r["text"]) > 500 else ""),
                "metadata": r["metadata"],
                "score": r["score"]
            })

        return jsonify({
            "query": query,
            "category": category_slug,
            "results": formatted,
            "count": len(formatted)
        })

    except Exception as e:
        logger.exception("RAG search failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rag/query", methods=["POST"])
def api_rag_query():
    """Full RAG query: semantic search + LLM generation."""
    if not RAG_AVAILABLE:
        return jsonify({"error": "RAG dependencies not available"}), 503

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    top_k = data.get("top_k", 5)
    chapter_filter = data.get("chapter_filter")
    content_type_filter = data.get("content_type_filter")
    topic_tags = data.get("topic_tags")
    show_sources = data.get("show_sources", True)
    category_slug = (data.get("category") or "").strip()

    if not question:
        return jsonify({"error": "Question is required"}), 400
    if not category_slug:
        return jsonify({"error": "A category is required."}), 400

    try:
        result = _rag_answer(
            question,
            top_k=top_k,
            chapter_filter=chapter_filter,
            content_type_filter=content_type_filter,
            topic_tags=topic_tags,
            show_sources=show_sources,
            category_slug=category_slug
        )

        return jsonify(result)

    except Exception as e:
        logger.exception("RAG query failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rag/config")
def api_rag_config():
    """Get current RAG configuration for a category (sanitized)."""
    if not RAG_AVAILABLE:
        return jsonify({"error": "RAG dependencies not available"}), 503

    category_slug = (request.args.get("category") or "").strip()
    config = _load_rag_config(category_slug, force_reload=True)
    # Return sanitized config (no API keys)
    return jsonify({
        "category": category_slug,
        "paths": config["paths"],
        "chunking": config["chunking"],
        "embeddings": {k: v for k, v in config["embeddings"].items() if k != "api_key"},
        "vectordb": config["vectordb"],
        "retrieval": config["retrieval"],
        "llm": {k: v for k, v in config["llm"].items() if k != "api_key"},
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
