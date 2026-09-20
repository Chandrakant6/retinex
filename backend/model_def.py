"""
Model architecture definition — shared by the training/build script and the
inference module so the two can never drift apart.

ARCHITECTURE IN SYNC WITH Retinex.ipynb: kept identical, layer for layer, to
cell 63 of the notebook used to train the currently-deployed checkpoint
(backend/checkpoints/model.keras). If the notebook's architecture changes on
a future retrain, mirror the change here too — see build_model() below.
"""
import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models

import processing

IMG_SIZE = 224
NUM_CLASSES = 5
# No layer names set in build_model() below, matching the notebook exactly.
# These two constants are still checked FIRST by get_grad_cam_layer() and
# get_logits_model() (in case you ever do add these names — to your own
# retrain or a different architecture entirely); when absent, both
# functions fall back to auto-detecting the right layer by type/position,
# which is what actually happens for a model built by build_model() as
# it stands today. See both functions below for exactly how.
LAST_CONV_LAYER_NAME = "last_conv"
LOGITS_LAYER_NAME = "icdr_logits"


def build_model() -> tf.keras.Model:
    """Architecture kept in exact sync with Retinex.ipynb (cell 63) — the
    notebook used to train the currently-deployed checkpoint. Deliberately
    identical to the notebook's version: no BatchNorm, Flatten (not
    GlobalAveragePooling) before the dense head, 5-way softmax output.
    scripts/train.py calls this function, so retraining through this
    project's script instead of the notebook produces the same
    architecture. If you change the notebook's architecture on a future
    retrain, mirror the change here too, or the two will drift apart.
    """
    return models.Sequential([
        layers.Input(shape=(IMG_SIZE, IMG_SIZE, 3)),

        layers.Conv2D(32, (3, 3), activation="relu"),
        layers.MaxPooling2D((2, 2)),

        layers.Conv2D(64, (3, 3), activation="relu"),
        layers.MaxPooling2D((2, 2)),

        layers.Conv2D(128, (3, 3), activation="relu"),
        layers.MaxPooling2D((2, 2)),

        layers.Flatten(),

        layers.Dense(128, activation="relu"),
        layers.Dropout(0.5),

        layers.Dense(NUM_CLASSES, activation="softmax"),
    ], name="dr_grader")



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


def build_grad_cam_model(model, conv_layer):
    """Build a Grad-CAM sub-model: given a loaded model and the conv layer
    to read gradients from (see get_grad_cam_layer), returns a Model
    outputting [conv_layer's activations, the model's final predictions].

    NOT implemented as the straightforward-looking
    `tf.keras.Model(inputs=model.inputs[0],
                     outputs=[conv_layer.output, model.outputs[0]])`
    — that pattern silently breaks for a Sequential model that has been
    saved and reloaded (confirmed directly: `tape.gradient(loss, conv_out)`
    returns None even though both `conv_layer.output` and `model.outputs[0]`
    individually look like valid, correctly-shaped tensors). This is a real
    Keras 3 quirk in how a reloaded Sequential model's internal graph
    represents shared lineage between an intermediate layer's output and
    the model's own output — a fresh Functional-API model built the normal
    way doesn't have this problem; only a *reloaded* Sequential model does.

    The fix: rebuild a clean Functional-API graph by re-calling the SAME
    (already-trained) layer objects in sequence. This reuses the identical
    weights — confirmed by comparing tensors before/after — while giving
    Keras a single, freshly-connected computation graph with no leftover
    Sequential-specific serialization quirks. Works equally well on a
    model that was never Sequential to begin with, so this is always safe
    to call.
    """
    inp = tf.keras.Input(shape=model.input_shape[1:])
    h = inp
    conv_out_tensor = None
    for layer in model.layers:
        h = layer(h)
        if layer is conv_layer:
            conv_out_tensor = h
    if conv_out_tensor is None:
        raise ValueError(f"Layer '{conv_layer.name}' not found while rebuilding the Grad-CAM graph.")
    return tf.keras.Model(inp, [conv_out_tensor, h])


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

    Plain [0,1] scaling ONLY — no ImageNet mean/std normalization. This
    matches Retinex.ipynb exactly (cells 39/43/48/52/53 all do
    `tf.cast(image, tf.float32) / 255.0` and nothing else). A trained
    model expects whatever numeric distribution it was trained on; adding
    a normalization step the notebook never used would feed the model
    input it has never seen, silently producing meaningless predictions
    even though nothing would crash. If you retrain with different
    normalization, update this function AND the notebook together.
    """
    return rgb_uint8.astype("float32") / 255.0


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

    NO SQUARE CROP — matches Retinex.ipynb exactly, which calls
    `tf.image.resize()` directly on the raw image (cells 39/43/48/52/53),
    with no field-of-view cropping step anywhere in the pipeline. APTOS
    2019's images are NOT square (checked directly: everything from
    1050x1050 up to 2848x4288, wildly mixed aspect ratios — see cell 24's
    output), so the model was trained on retinas anisotropically distorted
    (squished, not cropped) to fit 224x224. Matching that exactly — even
    though it reintroduces geometric distortion on non-square input — is
    necessary for the currently-deployed checkpoint to produce meaningful
    predictions at all: a model can only be evaluated fairly using the
    same preprocessing it learned under.

    processing.crop_to_square_array() still exists and is unused by
    default for exactly this reason. If you retrain with proper
    square-cropping added to the notebook's preprocessing, switch this
    function to call it again — search this file's git history (or
    doc/model.md) for the version that did.
    """
    img_bgr = cv2.imread(path)
    if img_bgr is None:
        raise FileNotFoundError(f"could not read image: {path}")
    resized_bgr = cv2.resize(img_bgr, (IMG_SIZE, IMG_SIZE))
    resized_rgb = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)
    return resized_rgb, preprocess_array(resized_rgb)
