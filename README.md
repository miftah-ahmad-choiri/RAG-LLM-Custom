# IBM Ceph Docs Scraper

A Flask web application that scrapes the IBM Storage Ceph 9.9.1 documentation
and converts every page into clean, structured Markdown notes.

## Quick Start

### 1. Install dependencies

```bash
cd ceph-scraper
pip install -r requirements.txt
playwright install chromium
```

### 2. Run the app

```bash
python app.py
```

Open your browser at **http://localhost:5000**

### 3. Use the UI

- The app auto-detects `IBM-Storage-Ceph-Documentation.md` (one level up)
- Click **Start Scraping** — watch the live log and progress bar
- When done, click **Download Markdown** to get your notes file
- Output files are saved in `ceph-scraper/output/`

---

## Project Structure

```
ceph-scraper/
├── app.py          # Flask routes & job management
├── parser.py       # Parses the .md index file → URL tree
├── scraper.py      # Fetches IBM docs pages (requests + playwright fallback)
├── converter.py    # HTML → clean Markdown conversion
├── requirements.txt
├── output/         # Generated Markdown notes land here
├── templates/
│   └── index.html  # Main UI
└── static/
    ├── style.css
    └── app.js
```

## Settings

| Setting | Default | Description |
|---|---|---|
| Use Playwright | ✅ On | Falls back to headless Chromium for JS-rendered pages |
| Rate limit | 1.5s | Delay between requests (be polite to IBM servers) |

## Notes on IBM Docs

IBM documentation is rendered by a React SPA. Plain HTTP requests may return
thin content. When that happens the scraper automatically falls back to
**Playwright** (headless Chromium), which waits for `networkidle` before
extracting content.

If you don't have Playwright available, uncheck **Use Playwright** in the UI
and the scraper will still work via plain HTTP where IBM serves static HTML.
