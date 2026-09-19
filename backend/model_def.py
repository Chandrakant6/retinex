"""
Model architecture definition — shared by the training/build script and the
inference module so the two can never drift apart.

A small custom CNN (not a huge pretrained backbone) on purpose: this sandbox
has no route to download ImageNet weights, and a compact network is fast
enough to run CPU-only on a district health-centre PC, which matters more
for this use case than squeezing out another point of accuracy. Swap in a
larger backbone (EfficientNet, ResNet) once real training compute and a
real dataset are available — nothing else in the pipeline needs to change
as long as the input size and output contract stay the same.
"""
import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models

import processing

IMG_SIZE = 224
NUM_CLASSES = 5
LAST_CONV_LAYER_NAME = "last_conv"
LOGITS_LAYER_NAME = "icdr_logits"


def build_model() -> tf.keras.Model:
    inputs = layers.Input(shape=(IMG_SIZE, IMG_SIZE, 3), name="fundus_image")

    x = layers.Conv2D(32, 3, padding="same", activation="relu")(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling2D()(x)

    x = layers.Conv2D(64, 3, padding="same", activation="relu")(x)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling2D()(x)

    x = layers.Conv2D(128, 3, padding="same", activation="relu")(x)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling2D()(x)

    x = layers.Conv2D(256, 3, padding="same", activation="relu", name=LAST_CONV_LAYER_NAME)(x)
    x = layers.BatchNormalization()(x)

    pooled = layers.GlobalAveragePooling2D()(x)
    pooled = layers.Dropout(0.3)(pooled)
    pooled = layers.Dense(128, activation="relu")(pooled)
    pooled = layers.Dropout(0.2)(pooled)
    # Logits kept as a separate, named layer (no activation) so inference
    # code can grab pre-softmax logits directly for temperature scaling —
    # much simpler and more robust than trying to invert a fused
    # Dense(activation="softmax") layer's output.
    logits = layers.Dense(NUM_CLASSES, activation=None, name=LOGITS_LAYER_NAME)(pooled)
    outputs = layers.Activation("softmax", name="icdr_probs")(logits)

    return models.Model(inputs, outputs, name="dr_grader")


def ensure_built(model):
    """A model saved without ever being 'built' (a Sequential model with no
    explicit Input layer, or any model never run on a batch before saving)
    has no defined .inputs/.outputs yet, which breaks every function below.
    A forward pass on a dummy batch forces Keras to resolve shapes; a
    harmless no-op for a model that's already built. Called once, right
    after tf.keras.models.load_model(), by ml_model.py, calibrate.py, and
    evaluate.py alike."""
    if not model.built:
        model(tf.zeros((1, IMG_SIZE, IMG_SIZE, 3), dtype=tf.float32))
    return model


def get_logits_model(model):
    """Build a sub-model that outputs pre-softmax logits, for temperature
    scaling and calibration. Shared by ml_model.py (inference),
    calibrate.py, and evaluate.py — one implementation, so a fix in one
    place can't drift out of sync with the others (see doc/model.md for a
    prior bug that happened exactly this way).

    Prefers the conventionally-named LOGITS_LAYER_NAME layer (what
    build_model() produces). If that layer doesn't exist — e.g. the model
    was trained by a different script that doesn't follow this project's
    architecture — falls back to neutralizing the final layer's softmax
    activation in place, so the model's own output becomes raw logits.
    This works for essentially any Keras classifier ending in a softmax
    Dense layer, trained however you like.
    """
    model_input = model.inputs[0]
    try:
        logits_layer = model.get_layer(LOGITS_LAYER_NAME)
        return tf.keras.Model(inputs=model_input, outputs=logits_layer.output)
    except ValueError:
        last_layer = model.layers[-1]
        if getattr(last_layer, "activation", None) is tf.keras.activations.softmax:
            last_layer.activation = tf.keras.activations.linear
            return tf.keras.Model(inputs=model_input, outputs=model.outputs[0])
        raise ValueError(
            f"No layer named '{LOGITS_LAYER_NAME}' and the final layer "
            f"('{last_layer.name}') activation isn't softmax — can't "
            f"determine logits automatically. Rename your final Dense "
            f"layer's activation to 'softmax', or add a layer named "
            f"'{LOGITS_LAYER_NAME}' before it."
        )


def get_grad_cam_layer(model):
    """Find the convolutional layer Grad-CAM should read gradients from.
    Shared by ml_model.py, for the same reason as get_logits_model above.

    Prefers the conventionally-named LAST_CONV_LAYER_NAME layer; falls
    back to the last Conv2D layer found by type, so this works on models
    trained by any script, not just this project's train.py."""
    try:
        return model.get_layer(LAST_CONV_LAYER_NAME)
    except ValueError:
        conv_candidates = [l for l in model.layers if isinstance(l, tf.keras.layers.Conv2D)]
        if not conv_candidates:
            raise ValueError(
                f"No layer named '{LAST_CONV_LAYER_NAME}' and no Conv2D "
                f"layer found at all — Grad-CAM needs at least one "
                f"convolutional layer. Existing layers: "
                f"{[l.name for l in model.layers]}"
            )
        return conv_candidates[-1]


def preprocess_array(rgb_uint8):
    """rgb_uint8: HxWx3 uint8 RGB array, already resized to IMG_SIZE.
    Standard [0,1] scaling + ImageNet-style mean/std normalization."""
    x = rgb_uint8.astype("float32") / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype="float32")
    std = np.array([0.229, 0.224, 0.225], dtype="float32")
    return (x - mean) / std


def preprocess_image_file(path: str):
    """THE single preprocessing path from an image file on disk to model
    input. Used by inference (ml_model.py), training (scripts/train.py) and
    calibration/evaluation (scripts/calibrate.py, evaluate.py) — all four
    call this instead of each rolling their own resize/normalize, because a
    previous version of this project had inference and calibration compute
    logits two subtly different ways and it silently broke calibration. One
    function, one contract, no drift.

    Returns (resized_rgb_uint8, normalized_float32) both at IMG_SIZE x
    IMG_SIZE. The uint8 version is for display/overlay purposes; the
    float32 version (unbatched, HxWx3) is what the model actually consumes.

    Crops to a square field-of-view bounding box BEFORE resizing — see
    processing.crop_to_square_array — so images of any input resolution or
    aspect ratio are resized without distortion. Idempotent on images that
    are already square (e.g. main.py's framed.png), so it's always safe to
    call regardless of what upstream step already ran.
    """
    img_bgr = cv2.imread(path)
    if img_bgr is None:
        raise FileNotFoundError(f"could not read image: {path}")
    square_bgr = processing.crop_to_square_array(img_bgr)
    resized_bgr = cv2.resize(square_bgr, (IMG_SIZE, IMG_SIZE))
    resized_rgb = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)
    return resized_rgb, preprocess_array(resized_rgb)
