"""
main.py

Entry point. Run from the VSCode terminal.

Usage examples:
  Single file:
      python main.py "Invoice March 2024" documents/invoice.pdf

  Whole folder (document_name = filename without extension):
      python main.py --folder documents/

  Test without uploading to Sheets:
      python main.py "Invoice March 2024" documents/invoice.pdf --dry-run
      python main.py --folder documents/ --dry-run
"""

import os
import sys
import json
import argparse

from quality_score import compute_quality
from upload_sheet  import upload_result


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


def process_file(document_name: str, file_path: str, dry_run: bool = False):
    """
    Runs the full pipeline for a single file:
      1. compute_quality  — loads, deskews, measures all metrics
      2. upload_result    — appends one row to Google Sheets (skipped if dry_run)
    """
    print(f"\n[ ] {file_path}")

    # Step 1 — quality metrics (deskew is automatic inside here)
    print("  [1/2] Computing quality metrics...")
    metrics = compute_quality(file_path)
    metrics["document_name"] = document_name

    # Print a summary to the terminal
    print(f"       blur={metrics['blur']}  "
          f"brightness={metrics['brightness']}  "
          f"contrast={metrics['contrast']}")
    print(f"       resolution={metrics['resolution']}  "
          f"noise={metrics['noise']}  "
          f"dpi={metrics['dpi']}")
    print(f"       quality_score = {metrics['quality_score']} / 100")

    # Step 2 — upload to Sheets
    if dry_run:
        print("  [2/2] Dry run — skipping Sheets upload.")
        print("        Full result:")
        print(json.dumps({k: float(v) if hasattr(v, "item") else v for k, v in metrics.items()}, indent=10))
    else:
        print("  [2/2] Uploading to Google Sheets...")
        upload_result(metrics)

    print(f"[OK] Done: {file_path}")
    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Document quality scorer → Google Sheets"
    )
    parser.add_argument(
        "document_name", nargs="?",
        help='Human-readable name, e.g. "Invoice March 2024"'
    )
    parser.add_argument(
        "file_path", nargs="?",
        help="Path to a single PDF, JPG, or PNG file"
    )
    parser.add_argument(
        "--folder", metavar="DIR",
        help="Process every supported file inside this folder"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compute metrics but do NOT upload to Google Sheets"
    )
    args = parser.parse_args()

    if args.folder:
        # ── Batch mode ───────────────────────────────────────────────────────
        folder = args.folder
        if not os.path.isdir(folder):
            print(f"Error: '{folder}' is not a valid folder.")
            sys.exit(1)

        files = sorted([
            f for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
        ])

        if not files:
            print(f"No supported files found in '{folder}'.")
            sys.exit(0)

        print(f"Found {len(files)} file(s) in '{folder}'.")
        for fname in files:
            doc_name = os.path.splitext(fname)[0]   # e.g. "invoice_march" from "invoice_march.pdf"
            process_file(doc_name, os.path.join(folder, fname), dry_run=args.dry_run)

    elif args.document_name and args.file_path:
        # ── Single file mode ─────────────────────────────────────────────────
        process_file(args.document_name, args.file_path, dry_run=args.dry_run)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()