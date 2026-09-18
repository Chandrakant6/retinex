"""
Image quality assessment and enhancement for fundus photographs.

Pure OpenCV — no MATLAB dependency in this build. Three-tier quality gate:

    score > GOOD_THRESHOLD        -> "good"      (used as-is)
    BORDERLINE_THRESHOLD..GOOD    -> "borderline" (enhanced, then re-checked)
    score < BORDERLINE_THRESHOLD  -> "reject"     (recapture guidance, no grading)

This mirrors real field conditions: portable fundus cameras produce a lot of
borderline images (slight blur, uneven lighting) that are still gradable
after enhancement, and a smaller number that genuinely need a retake.
"""
import cv2
import numpy as np

GOOD_THRESHOLD = 0.65
BORDERLINE_THRESHOLD = 0.45


def assess_quality(image_path: str) -> dict:
    """Evaluate focus, illumination and field-of-view. Returns a dict with
    a 0-1 score, a tier ('good' | 'borderline' | 'reject'), failure reasons,
    and human-readable recapture guidance (None if not needed)."""
    img = cv2.imread(image_path)
    if img is None:
        return {
            "tier": "reject", "gradable": False, "score": 0.0,
            "reasons": ["unreadable_file"],
            "guidance": "Could not read the uploaded file. Please upload a valid JPG/PNG.",
        }

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Focus: variance of the Laplacian (higher = sharper edges = better focus)
    focus = cv2.Laplacian(gray, cv2.CV_64F).var()

    # Illumination: mean brightness inside the retinal field (ignore black border)
    mask = gray > 10
    illum = float(gray[mask].mean()) if mask.any() else 0.0

    # Field of view: fraction of the frame occupied by the retinal circle
    fov = float(mask.sum()) / mask.size

    focus_score = min(focus / 150.0, 1.0)
    illum_score = max(0.0, 1.0 - abs(illum - 120) / 120.0)
    fov_score = min(fov / 0.35, 1.0)

    score = 0.5 * focus_score + 0.3 * illum_score + 0.2 * fov_score

    reasons = []
    if focus_score < 0.4:
        reasons.append("out_of_focus")
    if illum_score < 0.4:
        reasons.append("poor_illumination")
    if fov_score < 0.4:
        reasons.append("insufficient_field_of_view")

    if score > GOOD_THRESHOLD and not reasons:
        tier = "good"
    elif score > BORDERLINE_THRESHOLD:
        tier = "borderline"
    else:
        tier = "reject"

    guidance = None
    if tier == "reject":
        readable = ", ".join(r.replace("_", " ") for r in reasons) or "overall quality below threshold"
        guidance = f"Please recapture: {readable}."

    return {
        "tier": tier,
        "gradable": tier != "reject",
        "score": round(float(score), 3),
        "components": {
            "focus": round(float(focus_score), 3),
            "illumination": round(float(illum_score), 3),
            "field_of_view": round(float(fov_score), 3),
        },
        "reasons": reasons,
        "guidance": guidance,
    }


def enhance_image(image_path: str, out_path: str) -> str:
    """CLAHE on the L channel (illumination-robust contrast enhancement)
    plus mild edge-preserving denoise. Only called for 'borderline' images —
    'good' images are graded as-is so we never distort an already-clean photo."""
    img = cv2.imread(image_path)

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_eq = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge((l_eq, a, b)), cv2.COLOR_LAB2BGR)

    enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 3, 3, 7, 21)

    cv2.imwrite(out_path, enhanced)
    return out_path


def crop_to_square_array(img_bgr: np.ndarray, pad_frac: float = 0.02) -> np.ndarray:
    """Crop to a square bounding box around the circular retinal field of
    view, then pad to an exact square if the crop was clipped by the frame
    edge. Pure array in/out — no file I/O — so it can be called from
    model_def.preprocess_image_file() and reused identically by inference,
    training, calibration and evaluation. See standardize_frame() below for
    the full rationale; this is the array-only core it wraps.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    mask = (gray > 10).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((15, 15), np.uint8))

    ys, xs = np.where(mask)
    h, w = gray.shape
    if len(xs) == 0:
        side = max(h, w)
        canvas = np.zeros((side, side, 3), np.uint8)
        oy, ox = (side - h) // 2, (side - w) // 2
        canvas[oy:oy + h, ox:ox + w] = img_bgr
        return canvas

    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    radius = int(max(x1 - x0, y1 - y0) / 2 * (1 + pad_frac))

    x0c, x1c = max(cx - radius, 0), min(cx + radius, w)
    y0c, y1c = max(cy - radius, 0), min(cy + radius, h)
    cropped = img_bgr[y0c:y1c, x0c:x1c]

    side = max(cropped.shape[0], cropped.shape[1])
    canvas = np.zeros((side, side, 3), np.uint8)
    oy, ox = (side - cropped.shape[0]) // 2, (side - cropped.shape[1]) // 2
    canvas[oy:oy + cropped.shape[0], ox:ox + cropped.shape[1]] = cropped
    return canvas


def standardize_frame(image_path: str, out_path: str, pad_frac: float = 0.02) -> str:
    """File-based wrapper around crop_to_square_array — used by main.py to
    produce framed.png, the square base that enhancement, lesion detection
    and the model input are all derived from for a given screening request.

    WHY THIS EXISTS: fundus cameras produce wildly different resolutions and
    aspect ratios (4:3 phone photos, 16:9 crops, different manufacturers'
    default framing, different amounts of black border around the circular
    retina). Resizing a non-square frame straight to the model's 224x224
    input — the naive approach — stretches the circle into an ellipse and
    distorts vessel/lesion geometry differently depending on each image's
    original shape. Cropping to a square FIRST means the later resize is a
    uniform scale with no distortion, regardless of input resolution.

    This also matters for coordinate consistency: lesion points found by
    lesions.py and the model's Grad-CAM heatmap both need to refer to the
    same image frame so their locations can be compared (see
    ml_model._consistency_check). Running every later step on this same
    square image means "scale into 224x224 space" is always a single
    ratio — no crop offset to track.
    """
    img = cv2.imread(image_path)
    if img is None:
        cv2.imwrite(out_path, np.zeros((10, 10, 3), np.uint8))
        return out_path
    cv2.imwrite(out_path, crop_to_square_array(img, pad_frac))
    return out_path
