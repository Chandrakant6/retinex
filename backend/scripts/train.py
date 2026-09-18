"""
Fine-tune the DR grading model on a real labeled dataset.

Expected directory layout (standard "class subfolder" format — this is what
you get after re-sorting APTOS 2019 / IDRiD / Messidor-2 by ICDR label):

    data/
      train/
        0/  *.png or *.jpg   (No DR)
        1/                   (Mild NPDR)
        2/                   (Moderate NPDR)
        3/                   (Severe NPDR)
        4/                   (Proliferative DR)
      val/
        0/ 1/ 2/ 3/ 4/  (same structure, held out)

Usage:
    python scripts/train.py --data_dir data/ --epochs 15

Class imbalance is real for this task (roughly 35/25/25/10/5 in most public
DR datasets) — this script applies class weights computed from the training
split automatically. After training, run scripts/calibrate.py on the val
set before deploying (raw softmax confidences are not calibrated).

IMPORTANT: images are loaded through model_def.preprocess_image_file(),
the SAME function ml_model.py uses at inference time — including the
field-of-view square crop before resizing (see processing.crop_to_square_array
and doc/model.md). Do not swap this for tf.keras.utils.image_dataset_from_
directory's built-in resize: that resizes non-square source images directly,
which distorts the retinal circle differently depending on each image's
original aspect ratio, AND would silently diverge from what inference does
to a new upload — exactly the train/inference mismatch that quietly
collapses real-world sensitivity. One preprocessing function, used
everywhere, is the whole point.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import tensorflow as tf
from sklearn.utils.class_weight import compute_class_weight

from model_def import build_model, preprocess_image_file, IMG_SIZE

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "..", "checkpoints")
CLASS_NAMES = ["0", "1", "2", "3", "4"]


def list_files_and_labels(split_dir):
    paths, labels = [], []
    for cls_idx, cls_name in enumerate(CLASS_NAMES):
        cls_dir = os.path.join(split_dir, cls_name)
        if not os.path.isdir(cls_dir):
            continue
        for fname in sorted(os.listdir(cls_dir)):
            paths.append(os.path.join(cls_dir, fname))
            labels.append(cls_idx)
    if not paths:
        raise FileNotFoundError(f"No images found under {split_dir}/<0..4>/ — check --data_dir")
    return paths, labels


def make_dataset(paths, labels, batch_size, shuffle):
    def _load(path_tensor, label):
        path = path_tensor.numpy().decode("utf-8")
        _, x = preprocess_image_file(path)
        return x.astype("float32"), label

    def tf_load(path, label):
        x, label = tf.py_function(_load, [path, label], [tf.float32, tf.int32])
        x.set_shape((IMG_SIZE, IMG_SIZE, 3))
        label.set_shape(())
        return x, label

    ds = tf.data.Dataset.from_tensor_slices((paths, [int(l) for l in labels]))
    if shuffle:
        ds = ds.shuffle(buffer_size=len(paths), seed=42, reshuffle_each_iteration=True)
    ds = ds.map(tf_load, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", required=True)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    args = ap.parse_args()

    train_paths, train_labels = list_files_and_labels(os.path.join(args.data_dir, "train"))
    val_paths, val_labels = list_files_and_labels(os.path.join(args.data_dir, "val"))

    class_weights = compute_class_weight("balanced", classes=np.arange(5), y=train_labels)
    class_weight_dict = {i: float(w) for i, w in enumerate(class_weights)}
    print(f"Loaded {len(train_paths)} train / {len(val_paths)} val images")
    print("Class weights:", class_weight_dict)

    train_ds = make_dataset(train_paths, train_labels, args.batch_size, shuffle=True)
    val_ds = make_dataset(val_paths, val_labels, args.batch_size, shuffle=False)

    model = build_model()
    model.compile(
        optimizer=tf.keras.optimizers.Adam(args.lr),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            os.path.join(CHECKPOINT_DIR, "model.keras"),
            monitor="val_accuracy", save_best_only=True,
        ),
        tf.keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=4, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2),
    ]

    model.fit(
        train_ds, validation_data=val_ds, epochs=args.epochs,
        class_weight=class_weight_dict, callbacks=callbacks,
    )
    print("\nTraining done. Best weights saved to checkpoints/model.keras")
    print("Next: run scripts/calibrate.py, then scripts/evaluate.py — see doc/validation.md")


if __name__ == "__main__":
    main()
