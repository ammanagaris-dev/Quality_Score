"""
upload_sheet.py

Appends result rows to your Google Sheet using the service account.

Column order:
  document_name | file_name | blur | brightness | contrast |
  resolution | noise | dpi | quality_score | needs_rotation
"""
import gspread
from google.oauth2.service_account import Credentials

# ── EDIT THESE TWO LINES ONLY ────────────────────────────────────────────────
SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_ID       = "1NUJhlbnYXkKxk6s9Lu8Q3jb8bX7UA-PoqRuzxj_plKQ"
# ─────────────────────────────────────────────────────────────────────────────

SHEET_NAME = "Sheet1"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "document_name",
    "file_name",
    "blur",
    "brightness",
    "contrast",
    "resolution",
    "noise",
    "dpi",
    "quality_score",
    "needs_rotation",
]

# Worksheet is cached here after first connection
# so we only connect once per run, not once per file
_worksheet_cache = None
_headers_written = False


def _get_worksheet():
    global _worksheet_cache
    if _worksheet_cache is None:
        creds             = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client            = gspread.authorize(creds)
        sheet             = client.open_by_key(SPREADSHEET_ID)
        _worksheet_cache  = sheet.worksheet(SHEET_NAME)
    return _worksheet_cache


def _ensure_headers():
    """
    Write header row once per run only.
    Uses a module-level flag so we never read from the sheet
    more than once — avoids hitting the 429 rate limit.
    """
    global _headers_written
    if _headers_written:
        return
    ws = _get_worksheet()
    ws.update("A1", [HEADERS])
    print("  [sheet] Header row written.")
    _headers_written = True


def upload_result(metrics: dict):
    """
    Appends one row to the Google Sheet.

    Args:
        metrics: dict returned by quality_score.compute_quality(),
                 with 'document_name' already filled in by main.py.
    """
    _ensure_headers()

    row = [
        metrics.get("document_name",  ""),
        metrics.get("file_name",      ""),
        metrics.get("blur",           ""),
        metrics.get("brightness",     ""),
        metrics.get("contrast",       ""),
        metrics.get("resolution",     ""),
        metrics.get("noise",          ""),
        metrics.get("dpi",            ""),
        metrics.get("quality_score",  ""),
        metrics.get("needs_rotation", ""),
    ]

    ws = _get_worksheet()
    ws.append_row(row, value_input_option="USER_ENTERED")
    print(f"  [sheet] Uploaded — {metrics.get('file_name')} | "
          f"score: {metrics.get('quality_score')}/100 | "
          f"rotation: {metrics.get('needs_rotation')}")