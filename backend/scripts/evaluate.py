"""
ONE-TIME final evaluation on a held-out test set (e.g. Messidor-2, never
seen during training or calibration). Writes doc-ready metrics to
backend/metrics.json for the frontend Results page to display.

Also runs the "integrated pipeline vs single technique" comparison the
brief asks for:
    A) model alone, raw images, argmax threshold
    B) + quality gate (ungradeable images excluded)
    C) + quality gate + lesion safety net (flags referable if lesion
       evidence alone crosses a threshold, even when the model disagrees)

Usage:
    python scripts/evaluate.py --data_dir test_data/
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import tensorflow as tf

import processing
import lesions
from model_def import IMG_SIZE, get_logits_model, ensure_built, preprocess_image_file

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "..", "checkpoints", "model.keras")
METRICS_PATH = os.path.join(os.path.dirname(__file__), "..", "metrics.json")


def load_config():
    if os.path.exists(CONFIG_PATH):
        return json.load(open(CONFIG_PATH))
    return {"temperature": 1.0, "referable_threshold": 0.5}


def bootstrap_ci(tp, fn, tn, fp, n_boot=2000, seed=0):
    rng = np.random.RandomState(seed)
    pos = np.array([1] * tp + [0] * fn)   # 1 = correctly caught referable
    neg = np.array([1] * tn + [0] * fp)   # 1 = correctly caught non-referable
    sens_samples, spec_samples = [], []
    for _ in range(n_boot):
        if len(pos):
            sens_samples.append(rng.choice(pos, len(pos), replace=True).mean())
        if len(neg):
            spec_samples.append(rng.choice(neg, len(neg), replace=True).mean())
    def ci(arr):
        return (round(float(np.percentile(arr, 2.5)), 3), round(float(np.percentile(arr, 97.5)), 3))
    return ci(sens_samples) if sens_samples else (None, None), ci(spec_samples) if spec_samples else (None, None)


def confusion(preds, labels):
    tp = int(((preds == 1) & (labels == 1)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    tn = int(((preds == 0) & (labels == 0)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    sens = tp / max(tp + fn, 1)
    spec = tn / max(tn + fp, 1)
    return {"tp": tp, "fn": fn, "tn": tn, "fp": fp,
            "sensitivity": round(sens, 3), "specificity": round(spec, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", required=True, help="dir with 0/1/2/3/4 class subfolders, flat (test split)")
    args = ap.parse_args()

    cfg = load_config()
    model = tf.keras.models.load_model(CHECKPOINT_PATH)
    ensure_built(model)

    y_true, y_prob, quality_gradable, lesion_referable_floor = [], [], [], []
    logits_model = get_logits_model(model)

    for cls in range(5):
        cls_dir = os.path.join(args.data_dir, str(cls))
        if not os.path.isdir(cls_dir):
            print(f"  (skipping — no folder at {cls_dir})")
            continue
        n_before = len(y_true)
        for fname in os.listdir(cls_dir):
            path = os.path.join(cls_dir, fname)
            if not os.path.isfile(path):
                continue
            q = processing.assess_quality(path)
            quality_gradable.append(q["gradable"])

            _, x = preprocess_image_file(path)
            logits = logits_model(x[None, ...], training=False).numpy()[0]
            probs = tf.nn.softmax(logits / cfg["temperature"]).numpy()
            y_prob.append(probs)
            y_true.append(cls)

            ev = lesions.detect(path, "/tmp/_eval_lesion.png")
            lesion_referable_floor.append(lesions.rule_based_level_floor(ev) >= 2)
        print(f"  class {cls}: {len(y_true) - n_before} images from {cls_dir}")

    if len(y_true) == 0:
        raise FileNotFoundError(
            f"No images found under any of "
            f"{[os.path.join(args.data_dir, str(c)) for c in range(5)]}. "
            f"--data_dir must contain FLAT subfolders named 0, 1, 2, 3, 4 "
            f"directly inside it (each holding that class's images) — not "
            f"a train/val split. If you pointed this at the same data/ "
            f"used for training, use test_data/0..4/ (a held-out set) "
            f"instead, or pass e.g. data/val/ if you're evaluating the "
            f"validation split as a stand-in."
        )

    y_true = np.array(y_true)
    y_prob = np.array(y_prob)
    referable_true = (y_true >= 2).astype(int)
    referable_score = y_prob[:, 2:].sum(axis=1)
    quality_gradable = np.array(quality_gradable)
    lesion_referable_floor = np.array(lesion_referable_floor)

    # A) model alone, no quality gate
    pred_a = (referable_score >= cfg["referable_threshold"]).astype(int)
    conf_a = confusion(pred_a, referable_true)

    # B) + quality gate (rejected images excluded from the denominator,
    #    same as they'd never reach a grading decision in production)
    mask_b = quality_gradable
    conf_b = confusion(pred_a[mask_b], referable_true[mask_b])

    # C) + lesion safety net: referable if EITHER the model OR the lesion
    #    floor says so
    pred_c = (pred_a.astype(bool) | lesion_referable_floor).astype(int)
    conf_c = confusion(pred_c[mask_b], referable_true[mask_b])

    sens_ci, spec_ci = bootstrap_ci(conf_c["tp"], conf_c["fn"], conf_c["tn"], conf_c["fp"])

    metrics = {
        "n_test_images": int(len(y_true)),
        "config_used": cfg,
        "comparison": {
            "A_model_only": conf_a,
            "B_plus_quality_gate": conf_b,
            "C_plus_lesion_safety_net": conf_c,
        },
        "headline": {
            "sensitivity": conf_c["sensitivity"],
            "sensitivity_95ci": sens_ci,
            "specificity": conf_c["specificity"],
            "specificity_95ci": spec_ci,
            "meets_target": conf_c["sensitivity"] >= 0.90 and conf_c["specificity"] >= 0.85,
        },
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"\nWrote {METRICS_PATH}")


if __name__ == "__main__":
    main()
