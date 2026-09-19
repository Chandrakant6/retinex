"""
Temperature scaling + referable-threshold tuning on a held-out validation
set. Run this after training and BEFORE evaluate.py. Never tune on the
final test set — that's what evaluate.py is for, and only once.

Writes backend/config.json with:
    temperature          — softmax temperature that minimizes val NLL
    referable_threshold  — P(level>=2) cutoff hitting the sensitivity target

Usage:
    python scripts/calibrate.py --data_dir data/ --target_sensitivity 0.92
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import tensorflow as tf
from scipy.optimize import minimize_scalar

from model_def import IMG_SIZE, get_logits_model, ensure_built, preprocess_image_file
from train import list_files_and_labels

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "..", "checkpoints", "model.keras")


def get_val_logits(data_dir, model):
    """Loads validation images through model_def.preprocess_image_file —
    the same square-crop-then-resize pipeline used at inference and
    training time (see doc/model.md). A calibration fit on differently
    preprocessed images would produce a temperature/threshold that doesn't
    actually match production inference."""
    paths, labels = list_files_and_labels(os.path.join(data_dir, "val"))
    logits_layer_model = get_logits_model(model)

    all_logits = []
    batch = []
    for path in paths:
        _, x = preprocess_image_file(path)
        batch.append(x)
        if len(batch) == 16:
            all_logits.append(logits_layer_model(np.stack(batch), training=False).numpy())
            batch = []
    if batch:
        all_logits.append(logits_layer_model(np.stack(batch), training=False).numpy())

    return np.concatenate(all_logits), np.array(labels)


def fit_temperature(logits, labels):
    def nll(T):
        z = logits / T
        z = z - z.max(axis=1, keepdims=True)
        probs = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
        return -np.mean(np.log(probs[np.arange(len(labels)), labels] + 1e-8))

    result = minimize_scalar(nll, bounds=(0.1, 10.0), method="bounded")
    return float(result.x)


def expected_calibration_error(probs, labels, n_bins=10):
    conf = probs.max(axis=1)
    pred = probs.argmax(axis=1)
    correct = (pred == labels).astype(float)
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (conf > lo) & (conf <= hi)
        if mask.sum() == 0:
            continue
        ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)


def fit_threshold(probs, labels, target_sensitivity):
    referable_true = (labels >= 2).astype(int)
    referable_score = probs[:, 2:].sum(axis=1)
    thresholds = np.linspace(0.05, 0.95, 181)
    best = None
    for t in thresholds:
        pred = (referable_score >= t).astype(int)
        tp = ((pred == 1) & (referable_true == 1)).sum()
        fn = ((pred == 0) & (referable_true == 1)).sum()
        tn = ((pred == 0) & (referable_true == 0)).sum()
        fp = ((pred == 1) & (referable_true == 0)).sum()
        sens = tp / max(tp + fn, 1)
        spec = tn / max(tn + fp, 1)
        if sens >= target_sensitivity:
            # among thresholds meeting the sensitivity floor, pick the one
            # with the highest specificity
            if best is None or spec > best[1]:
                best = (float(t), float(spec), float(sens))
    return best  # (threshold, specificity, sensitivity) or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", required=True)
    ap.add_argument("--target_sensitivity", type=float, default=0.92)
    args = ap.parse_args()

    model = tf.keras.models.load_model(CHECKPOINT_PATH)
    ensure_built(model)
    logits, labels = get_val_logits(args.data_dir, model)

    T = fit_temperature(logits, labels)
    calibrated_probs = tf.nn.softmax(logits / T, axis=1).numpy()
    ece_before = expected_calibration_error(tf.nn.softmax(logits, axis=1).numpy(), labels)
    ece_after = expected_calibration_error(calibrated_probs, labels)

    result = fit_threshold(calibrated_probs, labels, args.target_sensitivity)
    if result is None:
        print(f"WARNING: no threshold reaches {args.target_sensitivity:.0%} sensitivity "
              f"on this validation set. Using 0.5 as a fallback — retrain or collect more data.")
        threshold = 0.5
    else:
        threshold, spec, sens = result
        print(f"Threshold {threshold:.3f} -> sensitivity {sens:.3f}, specificity {spec:.3f}")

    config = {"temperature": round(T, 4), "referable_threshold": round(threshold, 4)}
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nECE before calibration: {ece_before:.4f}")
    print(f"ECE after calibration:  {ece_after:.4f}")
    print(f"Wrote {CONFIG_PATH}: {config}")


if __name__ == "__main__":
    main()
