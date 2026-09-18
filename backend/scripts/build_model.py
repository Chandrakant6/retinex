"""
Creates checkpoints/model.keras so the app has something to load out of the
box, the FIRST time — before any real training has happened.

IMPORTANT: this produces an UNTRAINED model (random initialization). Once
you've trained real weights (scripts/train.py) or calibrated them
(scripts/calibrate.py), do NOT run this again without --force: it would
silently overwrite trained weights with fresh random ones, and there is no
undo. This script now refuses to overwrite an existing checkpoint unless
you pass --force, specifically to prevent that.

Usage:
    python scripts/build_model.py            # first-time setup only
    python scripts/build_model.py --force     # deliberately reset to untrained
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from model_def import build_model  # noqa: E402

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "..", "checkpoints")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                     help="Overwrite an existing checkpoint (e.g. trained weights) with a fresh untrained one.")
    args = ap.parse_args()

    out_path = os.path.join(CHECKPOINT_DIR, "model.keras")
    if os.path.exists(out_path) and not args.force:
        print(f"REFUSING to overwrite {os.path.abspath(out_path)} — it already exists.")
        print("If this is trained/calibrated weights, leave it alone.")
        print("If you really want a fresh untrained checkpoint, re-run with --force.")
        sys.exit(1)

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    model = build_model()
    model.summary()
    model.save(out_path)
    print(f"\nSaved untrained placeholder model to {os.path.abspath(out_path)}")
    print("Replace with real trained weights via scripts/train.py before evaluation.")


if __name__ == "__main__":
    main()
