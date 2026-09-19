"""
DR grading inference: preprocessing, forward pass, Grad-CAM, and the
lesion-consistency check that powers the "does the AI agree with visible
evidence?" flag in the review UI.

CONTRACT
--------
predict(original_path: str, enhanced_path: str, out_dir: str) -> dict

    {
        "icdr_level":    int,             # 0-4, argmax of calibrated probs
        "icdr_label":    str,
        "referable":     bool,            # P(level>=2) >= config threshold
        "referable_score": float,         # 0-1, calibrated
        "confidence":    float,           # 0-1, calibrated max-prob
        "probabilities": [float]*5,
        "evidence": {
            "microaneurysm_count": int,
            "hemorrhage_count": int,
            "exudate_area_pct": float,
            "cam_lesion_overlap_pct": float,   # % of lesion points inside the CAM hot region
            "consistent": bool,                # model grade vs. lesion floor agree
            "notes": [str],
        },
        "gradcam_path": str,     # heatmap-over-photo overlay, same size as input
        "lesions_path": str,     # annotated lesion overlay, same size as input
        "engine": "tensorflow" | "mock",
    }

Falls back to a deterministic mock (same pattern as the original
processing.py MATLAB/OpenCV fallback) if TensorFlow or the checkpoint isn't
available, so the API and frontend keep working during development.
"""
import hashlib
import json
import os

import cv2
import numpy as np

import lesions

BACKEND_DIR = os.path.dirname(__file__)
CHECKPOINT_PATH = os.path.join(BACKEND_DIR, "checkpoints", "model.keras")
CONFIG_PATH = os.path.join(BACKEND_DIR, "config.json")

ICDR_LABELS = {
    0: "No DR",
    1: "Mild NPDR",
    2: "Moderate NPDR",
    3: "Severe NPDR",
    4: "Proliferative DR",
}

RECOMMENDATIONS = {
    0: "Routine rescreen in 12 months",
    1: "Rescreen in 6-12 months",
    2: "Refer to ophthalmologist within 1 month",
    3: "Refer to ophthalmologist within 2 weeks",
    4: "Urgent referral (within days)",
}

# Semantic codes for the frontend to translate into the active display
# language (see frontend/src/i18n/translations.js, keys "rec_<code>").
# RECOMMENDATIONS above stays as an English fallback (used in the backend-
# rendered HTML report, and for any API consumer that just wants English).
RECOMMENDATION_CODES = {
    0: "routine_12mo",
    1: "routine_6to12mo",
    2: "refer_1mo",
    3: "refer_2wk",
    4: "urgent",
}

USE_TF = False
_model = None
_grad_model = None
_logits_model = None
_config = {"temperature": 1.0, "referable_threshold": 0.5}
IMG_SIZE = 224


def init_model():
    """Call once at app startup. Never raises — falls back to the mock."""
    global USE_TF, _model, _grad_model, _config
    global _logits_model
    try:
        import tensorflow as tf
        import model_def
        from model_def import LAST_CONV_LAYER_NAME, LOGITS_LAYER_NAME

        if not os.path.exists(CHECKPOINT_PATH):
            raise FileNotFoundError(
                f"{CHECKPOINT_PATH} not found — run `python scripts/build_model.py` first"
            )
        _model = tf.keras.models.load_model(CHECKPOINT_PATH)
        model_def.ensure_built(_model)
        model_input = _model.inputs[0]
        model_output = _model.outputs[0]

        conv_layer = model_def.get_grad_cam_layer(_model)
        if conv_layer.name != LAST_CONV_LAYER_NAME:
            print(f"[ml_model] No layer named '{LAST_CONV_LAYER_NAME}' — "
                  f"using last Conv2D layer found instead: '{conv_layer.name}'")
        _grad_model = tf.keras.Model(inputs=model_input, outputs=[conv_layer.output, model_output])

        try:
            _model.get_layer(LOGITS_LAYER_NAME)
        except ValueError:
            print(f"[ml_model] No layer named '{LOGITS_LAYER_NAME}' — "
                  f"neutralizing the final layer's softmax to read logits directly instead.")
        _logits_model = model_def.get_logits_model(_model)
        if os.path.exists(CONFIG_PATH):
            _config.update(json.load(open(CONFIG_PATH)))
        USE_TF = True
        print(f"[ml_model] TensorFlow model loaded from {CHECKPOINT_PATH}; config={_config}")
    except Exception as e:
        USE_TF = False
        print(f"[ml_model] TensorFlow model unavailable ({e}); using mock predictor")


def _preprocess(original_path):
    """Thin wrapper around model_def.preprocess_image_file — see that
    function's docstring for why preprocessing lives there and not here."""
    import model_def
    resized_rgb, x = model_def.preprocess_image_file(original_path)
    return resized_rgb, x[None, ...]  # (image for overlay, batched model input)


def _grad_cam(x, class_index):
    import tensorflow as tf

    with tf.GradientTape() as tape:
        conv_out, preds = _grad_model(x)
        loss = preds[:, class_index]
    grads = tape.gradient(loss, conv_out)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
    conv_out = conv_out[0]
    heatmap = tf.reduce_sum(conv_out * pooled_grads, axis=-1)
    heatmap = tf.maximum(heatmap, 0) / (tf.reduce_max(heatmap) + 1e-8)
    return heatmap.numpy()


def _resize_heatmap(heatmap, size_hw):
    """Resize a Grad-CAM activation map (values already in [0,1]) to
    (height, width). Used both for the small-resolution overlap check
    against lesion points, and for a full-resolution display overlay."""
    h, w = size_hw
    return cv2.resize(heatmap, (w, h))


def _blend_heatmap(rgb_img, heatmap_resized):
    heatmap_uint8 = np.uint8(255 * heatmap_resized)
    colored = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
    colored = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)
    return (0.55 * rgb_img + 0.45 * colored).astype(np.uint8)


def _consistency_check(icdr_level, evidence, cam_heatmap):
    floor = lesions.rule_based_level_floor(evidence)
    notes = []
    consistent = True

    if floor > icdr_level:
        consistent = False
        notes.append(f"Lesion evidence suggests at least level {floor}, model graded level {icdr_level}.")

    points = evidence["points"]["microaneurysms"] + evidence["points"]["hemorrhages"]
    if points:
        h, w = cam_heatmap.shape
        # points were detected on the full-res image; scale into heatmap coords
        # (caller passes points already scaled — see predict())
        inside = sum(1 for (px, py) in points if cam_heatmap[int(py), int(px)] > 0.5)
        overlap_pct = round(100.0 * inside / len(points), 1)
        if overlap_pct < 30:
            consistent = False
            notes.append("Most detected lesions fall outside the model's attention region.")
    else:
        overlap_pct = None

    return consistent, overlap_pct, notes


def predict(original_path: str, enhanced_path: str, out_dir: str) -> dict:
    if USE_TF:
        try:
            return _predict_tf(original_path, enhanced_path, out_dir)
        except Exception as e:
            print(f"[ml_model] TensorFlow inference failed ({e}); falling back to mock for this image")
    return _predict_mock(original_path, enhanced_path, out_dir)


def _predict_tf(original_path, enhanced_path, out_dir):
    import tensorflow as tf

    base_rgb_224, x = _preprocess(original_path)
    T = _config["temperature"]
    logit_vals = _logits_model(x, training=False).numpy()[0]
    probs = tf.nn.softmax(logit_vals / T).numpy()

    level = int(np.argmax(probs))
    referable_score = float(probs[2:].sum())

    heatmap = _grad_cam(x, level)  # 28x28, values in [0,1]

    # Full-resolution display overlay: blend onto the framed image at ITS
    # native resolution (not the 224x224 model-input size), so the Grad-CAM
    # tab isn't blurrier than the Enhanced/Lesions tabs it's compared
    # against in the UI. `original_path` here is the square-framed image
    # (see processing.standardize_frame), so this is a plain resize with
    # no aspect distortion.
    full_bgr = cv2.imread(original_path)
    full_rgb = cv2.cvtColor(full_bgr, cv2.COLOR_BGR2RGB)
    heatmap_full = _resize_heatmap(heatmap, full_rgb.shape[:2])
    overlay_full = _blend_heatmap(full_rgb, heatmap_full)
    gradcam_path = os.path.join(out_dir, "gradcam.png")
    cv2.imwrite(gradcam_path, cv2.cvtColor(overlay_full, cv2.COLOR_RGB2BGR))

    # Separate small-resolution heatmap (224x224) purely for the
    # lesion/attention overlap check below — this doesn't need to be
    # high-resolution, it's a coordinate lookup, not something displayed.
    heatmap_224 = _resize_heatmap(heatmap, (IMG_SIZE, IMG_SIZE))

    lesions_path = os.path.join(out_dir, "lesions.png")
    evidence_raw = lesions.detect(enhanced_path, lesions_path)

    # scale lesion points from the enhanced image's resolution into 224x224
    # heatmap coordinates for the overlap check. Both enhanced_path and
    # original_path are the same square-framed image (just possibly
    # enhanced vs. not), so this is a single uniform ratio — no crop
    # offset to account for.
    enh_img = cv2.imread(enhanced_path)
    eh, ew = enh_img.shape[:2]
    def scale_points(pts):
        return [(px * IMG_SIZE / ew, py * IMG_SIZE / eh) for px, py in pts]

    evidence_scaled = dict(evidence_raw)
    evidence_scaled["points"] = {
        "microaneurysms": scale_points(evidence_raw["points"]["microaneurysms"]),
        "hemorrhages": scale_points(evidence_raw["points"]["hemorrhages"]),
    }
    consistent, overlap_pct, notes = _consistency_check(level, evidence_scaled, heatmap_224)

    return {
        "icdr_level": level,
        "icdr_label": ICDR_LABELS[level],
        "referable": referable_score >= _config["referable_threshold"],
        "referable_score": round(referable_score, 3),
        "confidence": round(float(probs.max()), 3),
        "probabilities": [round(float(p), 3) for p in probs],
        "recommendation": RECOMMENDATIONS[level],
        "recommendation_code": RECOMMENDATION_CODES[level],
        "evidence": {
            "microaneurysm_count": evidence_raw["microaneurysm_count"],
            "hemorrhage_count": evidence_raw["hemorrhage_count"],
            "exudate_area_pct": evidence_raw["exudate_area_pct"],
            "cam_lesion_overlap_pct": overlap_pct,
            "consistent": consistent,
            "notes": notes,
        },
        "gradcam_path": gradcam_path,
        "lesions_path": lesions_path,
        "engine": "tensorflow",
    }


def _predict_mock(original_path, enhanced_path, out_dir):
    """Deterministic mock: same image bytes -> same result, so demo/dev is
    repeatable. Still runs real lesion detection (that part has no TF
    dependency) so the UI's evidence panel works identically either way."""
    import random

    seed = int(hashlib.md5(open(original_path, "rb").read()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    level = rng.choices([0, 1, 2, 3, 4], weights=[35, 25, 25, 10, 5])[0]
    probs = np.full(5, 0.03)
    probs[level] = 0.6 + rng.random() * 0.3
    probs = probs / probs.sum()

    img = cv2.imread(original_path)
    h, w = img.shape[:2]

    heat = np.zeros((h, w), np.float32)
    cx, cy = rng.randint(w // 4, 3 * w // 4), rng.randint(h // 4, 3 * h // 4)
    cv2.circle(heat, (cx, cy), max(w, h) // 8, 1.0, -1)
    heat = cv2.GaussianBlur(heat, (0, 0), sigmaX=w / 15)
    heat = heat / (heat.max() + 1e-8)
    colored = cv2.applyColorMap(np.uint8(255 * heat), cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(img, 0.55, colored, 0.45, 0)
    gradcam_path = os.path.join(out_dir, "gradcam.png")
    cv2.imwrite(gradcam_path, overlay)

    lesions_path = os.path.join(out_dir, "lesions.png")
    evidence_raw = lesions.detect(enhanced_path, lesions_path)
    consistent, overlap_pct, notes = _consistency_check(level, evidence_raw, heat)
    notes.append("MOCK PREDICTION — no trained model loaded. See doc/model.md.")

    return {
        "icdr_level": level,
        "icdr_label": ICDR_LABELS[level],
        "referable": level >= 2,
        "referable_score": round(float(probs[2:].sum()), 3),
        "confidence": round(float(probs.max()), 3),
        "probabilities": [round(float(p), 3) for p in probs],
        "recommendation": RECOMMENDATIONS[level],
        "recommendation_code": RECOMMENDATION_CODES[level],
        "evidence": {
            "microaneurysm_count": evidence_raw["microaneurysm_count"],
            "hemorrhage_count": evidence_raw["hemorrhage_count"],
            "exudate_area_pct": evidence_raw["exudate_area_pct"],
            "cam_lesion_overlap_pct": overlap_pct,
            "consistent": consistent,
            "notes": notes,
        },
        "gradcam_path": gradcam_path,
        "lesions_path": lesions_path,
        "engine": "mock",
    }
