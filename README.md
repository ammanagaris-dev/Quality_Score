# Quality_Score

An automated document quality assessment system that analyses insurance claim documents and logs quality metrics to Google Sheets.

## Overview

Quality_Score processes PDF and image documents through a three-stage pipeline:

- **Orientation Fix** — detects and corrects landscape documents (rotates to portrait)
- **Deskew** — detects and corrects small tilt angles using Hough Line Transform
- **Quality Analysis** — computes 6 raw metrics and an overall quality score

Results are automatically uploaded to a shared Google Sheet for team review.

## Metrics

| Metric | Description |
|--------|-------------|
| `blur` | Laplacian variance — higher means sharper |
| `brightness` | Mean pixel intensity (0–255) |
| `contrast` | Standard deviation of pixel intensities |
| `resolution` | Total megapixels (e.g. 3.86 MP) |
| `noise` | Mean noise level — lower means cleaner |
| `dpi` | Dots per inch from image metadata |
| `quality_score` | Weighted score out of 100 |
| `needs_rotation` | `Yes` if document was landscape and corrected |

## Quick Start

```bash
# Clone the repo
git clone https://github.com/YourUsername/Quality_Score.git
cd Quality_Score

# Install dependencies
pip install -r requirements.txt

# Install Poppler (required for PDF processing)
# Windows  → https://github.com/oschwartz10612/poppler-windows/releases
#             extract zip, add bin\ folder to system PATH, restart terminal
# Mac      → brew install poppler
# Ubuntu   → sudo apt install poppler-utils

# Get service_account.json from your team lead
# Place it in the root of this folder

# Run
python main.py --folder "C:\path\to\documents"
```

## Usage

```bash
# Process a single file
python main.py "Document Name" "C:\path\to\file.pdf"

# Process an entire folder
python main.py --folder "C:\path\to\folder"

# Dry run — compute metrics without uploading to Sheets
python main.py --folder "C:\path\to\folder" --dry-run
```

## Project Structure

```
Quality_Score/
├── main.py               — entry point, connects pipeline to Sheets
├── quality_score.py      — orientation fix, deskew, all metric computation
├── upload_sheet.py       — Google Sheets authentication and row upload
├── requirements.txt      — Python dependencies
├── .gitignore
└── service_account.json  — not in repo, obtain from team lead
```

## Google Sheets Output

Each document processed appends one row:

| document_name | file_name | blur | brightness | contrast | resolution | noise | dpi | quality_score |
|---------------|-----------|------|------------|----------|------------|-------|-----|---------------|
| Claim_Form_Dec | Claim_Form.JPG | 2043.88 | 234.13 | 47.04 | 3.86 | 7.15 | 200 | 78 |

## Dependencies

| Library         | Purpose                                          |
|-----------------|--------------------------------------------------|
| `opencv-python` | Image loading, deskew, all metric computation    |
| `numpy`         | Pixel array math and median angle calculation    |
| `Pillow`        | Reading DPI metadata from image files            |
| `pdf2image`     | Rendering PDF pages to images (requires Poppler) |
| `gspread`       | Google Sheets API wrapper                        |
| `google-auth`   | Service account authentication                   |

## Notes

- `service_account.json` is excluded from the repo via `.gitignore` — never commit it
- PDFs are rendered at 150 DPI internally for processing
- When using `--folder`, `document_name` is set automatically from the filename