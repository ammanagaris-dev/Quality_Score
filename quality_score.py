"""
quality_score.py

Loads a document (PDF or image), deskews it if tilted, then computes
raw quality metrics — no normalization, no dividing.
All values rounded to 2 decimal places.

Metrics returned:
  blur        — Laplacian variance (higher = sharper, e.g. 0 to 1000+)
  brightness  — mean pixel intensity 0–255
  contrast    — standard deviation of pixel intensities 0–128+
  resolution  — total megapixels (e.g. 2.1 MP)
  noise       — mean absolute difference vs blurred image (lower = cleaner)
  dpi         — from image metadata
  quality_score — weighted score out of 100, derived from raw values
"""

import os
import numpy as np
import cv2
from PIL import Image


# ── 1. LOAD ──────────────────────────────────────────────────────────────────

def _load_image_array(file_path: str) -> np.ndarray:
    """
    Converts any supported file into a BGR numpy array for OpenCV.
    PDFs: renders the first page at 150 DPI using Poppler.
    Images: reads directly with OpenCV.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        import pdf2image
        pages = pdf2image.convert_from_path(
            file_path, first_page=1, last_page=1, dpi=150
        )
        if not pages:
            raise ValueError("Could not render PDF — is Poppler installed?")
        return cv2.cvtColor(np.array(pages[0]), cv2.COLOR_RGB2BGR)
    else:
        arr = cv2.imread(file_path)
        if arr is None:
            raise ValueError(f"Could not read image: {file_path}")
        return arr


def _get_dpi(file_path: str) -> float:
    """
    Reads DPI from image metadata.
    PDFs are rendered at 150 DPI, so always returns 150.0 for them.
    Falls back to 72.0 if metadata is missing.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return 150.0
    try:
        img      = Image.open(file_path)
        dpi_info = img.info.get("dpi", (72, 72))
        return float(dpi_info[0])
    except Exception:
        return 72.0


# ── 2. DESKEW ────────────────────────────────────────────────────────────────

def _detect_skew_angle(gray: np.ndarray) -> float:
    """
    Uses Hough Line Transform to find the tilt angle of a document.
    Returns the median angle of all near-horizontal lines detected.
    Returns 0.0 if no lines are found.
    """
    _, thresh = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    edges = cv2.Canny(thresh, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=100,
        minLineLength=100,
        maxLineGap=10,
    )
    if lines is None:
        return 0.0

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 == x1:
            continue
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if -45 < angle < 45:
            angles.append(angle)

    return float(np.median(angles)) if angles else 0.0


def _rotate_image(img: np.ndarray, angle: float) -> np.ndarray:
    """Rotates image by angle degrees. Fills new border pixels with white."""
    h, w = img.shape[:2]
    M    = cv2.getRotationMatrix2D((w // 2, h // 2), angle, scale=1.0)
    return cv2.warpAffine(
        img, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def _deskew(img: np.ndarray) -> tuple:
    """
    Detects and corrects document tilt.
    Skips if angle < 0.5° (invisible) or > 45° (likely misdetection).
    Returns (corrected_image, angle_applied).
    """
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    angle = _detect_skew_angle(gray)

    if abs(angle) < 0.5:
        return img, 0.0
    if abs(angle) > 45.0:
        print(f"  [deskew] Angle {angle:.1f}° exceeds limit — skipping.")
        return img, 0.0

    return _rotate_image(img, angle), angle


# ── 3. RAW METRICS ───────────────────────────────────────────────────────────

def _blur_score(img: np.ndarray) -> float:
    """
    Laplacian variance — raw value, not normalized.
    Higher = sharper. Typical range: 0 (very blurry) to 1000+ (very sharp).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2)


def _brightness_score(img: np.ndarray) -> float:
    """
    Mean pixel intensity — raw value.
    Range: 0 (black) to 255 (white).
    Good document range: ~100–220.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return round(float(gray.mean()), 2)


def _contrast_score(img: np.ndarray) -> float:
    """
    Standard deviation of pixel intensities — raw value.
    Range: 0 (flat grey) to ~128+ (high contrast).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return round(float(gray.std()), 2)


def _noise_score(img: np.ndarray) -> float:
    """
    Mean absolute difference between original and Gaussian-blurred image.
    Raw value — lower = cleaner. Typical range: 0 (clean) to 20+ (noisy).
    """
    gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    diff    = np.abs(gray.astype(np.float32) - blurred.astype(np.float32)).mean()
    return round(float(diff), 2)


def _resolution_score(img: np.ndarray) -> float:
    """
    Total megapixels — raw value.
    e.g. a 1920x1080 image = 2.07 MP.
    """
    h, w = img.shape[:2]
    return round((w * h) / 1_000_000, 2)


# ── 4. QUALITY SCORE ─────────────────────────────────────────────────────────

def _compute_quality_score(
    blur: float,
    brightness: float,
    contrast: float,
    noise: float,
    resolution: float,
) -> int:
    """
    Converts raw metric values into a single score out of 100.

    Each raw metric is capped against a realistic maximum for documents,
    then weighted. No arbitrary normalization — all caps are based on
    what a genuinely good document looks like:

      blur       cap=500   — sharp document scan is ~200–500 Laplacian variance
      brightness cap=255   — raw pixel mean, ideal ~120–200
      contrast   cap=80    — good document std dev is ~40–80
      noise      lower=better, penalty applied above 5.0
      resolution cap=3MP   — most scanned docs are 1–3MP

    Weights:
      blur        35%
      contrast    25%
      noise       20%
      resolution  10%
      brightness  10%  (with penalty for too dark or overexposed)
    """
    blur_s       = min(blur / 500.0, 1.0)
    contrast_s   = min(contrast / 80.0, 1.0)
    noise_s      = max(0.0, 1.0 - (noise / 10.0))   # noise > 10 = bad
    resolution_s = min(resolution / 3.0, 1.0)

    # Brightness: ideal raw value is ~160 (light background, dark text)
    # Penalty increases the further it is from 160
    brightness_s = max(0.0, 1.0 - abs(brightness - 160) / 160.0)

    raw = (
        blur_s       * 0.35 +
        contrast_s   * 0.25 +
        noise_s      * 0.20 +
        resolution_s * 0.10 +
        brightness_s * 0.10
    )
    return int(round(raw * 100))


# ── 5. PUBLIC ENTRY POINT ────────────────────────────────────────────────────

def compute_quality(file_path: str) -> dict:
    """
    Full pipeline: load → deskew → compute raw metrics → compute score.

    Returns dict with keys:
        document_name  (empty, filled by main.py)
        file_name
        blur           raw Laplacian variance
        brightness     raw mean pixel intensity (0–255)
        contrast       raw pixel std deviation
        resolution     megapixels
        noise          raw mean noise level
        dpi
        quality_score  0–100
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    img = _load_image_array(file_path)
    dpi = _get_dpi(file_path)

    img, skew_angle = _deskew(img)
    if skew_angle != 0.0:
        print(f"  [deskew] Corrected tilt: {skew_angle:.2f} degrees.")

    blur       = _blur_score(img)
    brightness = _brightness_score(img)
    contrast   = _contrast_score(img)
    resolution = _resolution_score(img)
    noise      = _noise_score(img)

    return {
        "document_name": "",
        "file_name":     os.path.basename(file_path),
        "blur":          blur,
        "brightness":    brightness,
        "contrast":      contrast,
        "resolution":    resolution,
        "noise":         noise,
        "dpi":           round(dpi, 2),
        "quality_score": _compute_quality_score(blur, brightness, contrast, noise, resolution),
    }


# ── standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python quality_score.py <path_to_file>")
        sys.exit(1)
    print(json.dumps(compute_quality(sys.argv[1]), indent=2))