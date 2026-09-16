"""
Image quality assessment + enhancement.

Tries MATLAB (Image Processing Toolbox) first. If the MATLAB engine isn't
installed/available, silently falls back to an equivalent OpenCV
implementation so the app always runs — MATLAB downtime never blocks the demo.

Each function returns which engine actually ran, in the "engine" field,
so you always know what powered a given result.
"""
import os
import cv2
import numpy as np

USE_MATLAB = False
_eng = None

MATLAB_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "matlab_src")


def init_matlab():
    """Call once at app startup. Never raises — falls back silently."""
    global USE_MATLAB, _eng
    try:
        import matlab.engine  # noqa: F401 (import kept local; only needed if installed)
        _eng = matlab.engine.start_matlab()
        _eng.addpath(os.path.abspath(MATLAB_SRC_DIR), nargout=0)
        USE_MATLAB = True
        print("[matlab] engine started, using MATLAB for image processing")
    except Exception as e:
        USE_MATLAB = False
        print(f"[matlab] unavailable ({e}); using OpenCV fallback")


# ---------------------------------------------------------------- quality --

def assess_quality(image_path: str) -> dict:
    if USE_MATLAB:
        try:
            r = _eng.assess_quality(image_path)
            return _matlab_struct_to_dict(r)
        except Exception as e:
            print(f"[matlab] assess_quality failed ({e}); falling back to OpenCV")
    return _assess_quality_cv(image_path)


def _assess_quality_cv(image_path: str) -> dict:
    img = cv2.imread(image_path)
    if img is None:
        return {
            "gradable": False, "score": 0.0,
            "reasons": ["unreadable_file"],
            "guidance": "Could not read the uploaded file. Please upload a valid JPG/PNG.",
            "engine": "opencv",
        }

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Focus: variance of Laplacian (higher = sharper)
    focus = cv2.Laplacian(gray, cv2.CV_64F).var()

    # Illumination: mean brightness over the retinal (non-black) region
    mask = gray > 10
    illum = float(gray[mask].mean()) if mask.any() else 0.0

    # Field of view: fraction of frame occupied by the retinal circle
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

    gradable = score > 0.45 and not reasons
    guidance = None
    if not gradable:
        readable_reasons = ", ".join(r.replace("_", " ") for r in reasons) or "quality below threshold"
        guidance = f"Please recapture: {readable_reasons}."

    return {
        "gradable": bool(gradable),
        "score": round(float(score), 3),
        "reasons": reasons,
        "guidance": guidance,
        "engine": "opencv",
    }


# --------------------------------------------------------------- enhance --

def enhance_image(image_path: str, out_path: str) -> dict:
    if USE_MATLAB:
        try:
            result_path = _eng.enhance_image(image_path, out_path)
            return {"path": str(result_path), "engine": "matlab"}
        except Exception as e:
            print(f"[matlab] enhance_image failed ({e}); falling back to OpenCV")
    return _enhance_cv(image_path, out_path)


def _enhance_cv(image_path: str, out_path: str) -> dict:
    img = cv2.imread(image_path)

    # CLAHE on the L channel (illumination-robust contrast enhancement)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_eq = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge((l_eq, a, b)), cv2.COLOR_LAB2BGR)

    # Mild denoise
    enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 3, 3, 7, 21)

    cv2.imwrite(out_path, enhanced)
    return {"path": out_path, "engine": "opencv"}


# ------------------------------------------------------------------ util --

def _matlab_struct_to_dict(r) -> dict:
    d = dict(r)
    if "reasons" in d:
        d["reasons"] = list(d["reasons"])
    if not d.get("guidance"):
        d["guidance"] = None
    d["engine"] = "matlab"
    return d
