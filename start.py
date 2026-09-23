"""
start.py — Self-contained launcher for the IBM Ceph RAG app.

Run with ANY python on the machine:
    python start.py

It will:
  1. Create .venv if missing
  2. pip install -r requirements.txt if flask is not yet installed
  3. Launch app.py using .venv/Scripts/python.exe
"""

import sys
import subprocess
from pathlib import Path

ROOT        = Path(__file__).parent.resolve()
VENV_DIR    = ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
VENV_PIP    = VENV_DIR / "Scripts" / "pip.exe"
REQUIREMENTS = ROOT / "requirements.txt"

# ── 1. Create .venv using whatever python is running this script ───────────
if not VENV_PYTHON.exists():
    print("=== Creating virtual environment in .venv/ ===")
    r = subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if r.returncode != 0:
        print("ERROR: Could not create .venv. Is Python 3.11+ installed?")
        sys.exit(1)
    print()

# ── 2. Install dependencies if flask is missing ────────────────────────────
check = subprocess.run(
    [str(VENV_PYTHON), "-c", "import flask"],
    capture_output=True
)
if check.returncode != 0:
    print("=== Installing dependencies (first run — takes a few minutes) ===")
    r = subprocess.run([
        str(VENV_PIP), "install",
        "-r", str(REQUIREMENTS),
        "--extra-index-url", "https://download.pytorch.org/whl/cpu"
    ])
    if r.returncode != 0:
        print("\nERROR: pip install failed. See output above.")
        sys.exit(1)
    print()

# ── 3. Launch app.py with the venv interpreter ─────────────────────────────
print("=== Starting IBM Ceph RAG ===")
subprocess.run(
    [str(VENV_PYTHON), str(ROOT / "app.py")] + sys.argv[1:],
    cwd=str(ROOT)
)
