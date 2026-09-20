# The Model

## Current status: architecture and preprocessing now match Retinex.ipynb exactly

**Read this first.** `backend/checkpoints/model.keras` holds weights
trained via `Retinex.ipynb` (the notebook, not this project's own
`scripts/train.py`) on APTOS 2019. `model_def.py` and `ml_model.py` have
been rewritten to match that notebook's architecture and preprocessing
exactly — this matters more than it might sound like: a model can only be
evaluated fairly using the same preprocessing it learned under, and this
notebook's preprocessing differs from what this project originally used
in two ways significant enough to silently produce meaningless
predictions if not matched precisely:

- **No square field-of-view crop.** The notebook resizes raw images
  directly (`tf.image.resize`), with no cropping step anywhere. APTOS
  2019's images are NOT square — checked directly against the notebook's
  own output: everything from 1050×1050 up through 2848×4288, wildly
  mixed aspect ratios. The model was trained on retinas anisotropically
  distorted (squished, not cropped) to fit 224×224. `model_def.py` matches
  this exactly now — see `preprocess_image_file()`'s docstring.
- **Plain [0,1] scaling, no ImageNet normalization.** The notebook does
  `tf.cast(image, tf.float32) / 255.0` and nothing else — no mean/std
  subtraction. `preprocess_array()` matches this exactly now.

A few things are still true regardless of this fix:

- **Confidence scores are uncalibrated** (`config.json` still has
  `temperature: 1.0`). A model can be well-trained and still say "91%
  confident" when it's right 70% of the time.
- **The referable decision threshold is still the untuned default (0.5).**
  `scripts/calibrate.py` hasn't run yet.
- **No held-out evaluation has been run**, so there are no real
  sensitivity/specificity numbers yet.
- **A likely methodology gap in the notebook itself, flagged but not yet
  fixed (by request):** the notebook's `.fit()` calls don't pass
  `validation_data=`, even though `EarlyStopping`/`ReduceLROnPlateau` both
  monitor `val_loss` — those callbacks likely never fired. The reported
  test evaluation (classification report, confusion matrix) also appears
  to reuse the training dataframe rather than a genuinely held-out split
  (`train_test_split` is imported but not visibly called). This means the
  notebook's own reported accuracy may not reflect real generalization.
  Worth fixing before trusting any accuracy number from the notebook
  itself, independent of the calibration/evaluation steps below.

**The immediate next steps, in order:**
```bash
cd backend
python scripts/calibrate.py --data_dir data/ --target_sensitivity 0.92
python scripts/evaluate.py --data_dir test_data/   # a genuinely held-out set
```
See `doc/validation.md` for what each of these produces and how to report
it honestly.

## Architecture (`backend/model_def.py`)

Kept in exact sync with `Retinex.ipynb` (cell 63) — a Sequential CNN, no
BatchNorm, `Flatten` (not global pooling) before the dense head:

```
Input (224×224×3)
→ Conv2D(32, 3×3, relu) → MaxPool(2×2)
→ Conv2D(64, 3×3, relu) → MaxPool(2×2)
→ Conv2D(128, 3×3, relu) → MaxPool(2×2)     ← Grad-CAM reads this layer (auto-detected)
→ Flatten
→ Dense(128, relu) → Dropout(0.5)
→ Dense(5, softmax)                          ← auto-detected for logits (see below)
```

~11.2M parameters (most of it in the Flatten→Dense(128) transition —
86,528 flattened features into 128 units is over 11M weights on its own;
this is the direct cost of `Flatten` instead of pooling, and matches the
notebook's design as-is rather than a change made here).

**No layer names are set, matching the notebook exactly.** `ml_model.py`
doesn't need them — `model_def.get_grad_cam_layer()` and
`get_logits_model()` auto-detect the right layers by type/position:
the last `Conv2D` layer by type for Grad-CAM, and (since there's no
separate pre-softmax logits layer here) a technique that neutralizes the
final layer's softmax activation in place so the model's own output
becomes raw logits directly — confirmed correct by checking the output no
longer sums to 1 after neutralizing. This is what lets this project's
inference code work against a checkpoint trained by *any* script, not
just one that follows a particular naming convention.

**A real bug caught and fixed while wiring this architecture up:**
building a Grad-CAM sub-model the straightforward way —
`tf.keras.Model(inputs=model.inputs[0], outputs=[conv_layer.output,
model.outputs[0]])` — silently produces `None` gradients for a *Sequential*
model that has been saved and reloaded (confirmed directly: both
`conv_layer.output` and `model.outputs[0]` individually look like valid,
correctly-shaped tensors, but `tape.gradient()` between them returns
`None` anyway). This is a real Keras 3 quirk in how a reloaded Sequential
model's internal graph represents shared lineage between an intermediate
layer's output and the model's own final output. The fix —
`model_def.build_grad_cam_model()` — rebuilds a clean Functional-API graph
by re-calling the *same* already-trained layer objects in sequence, which
reuses the identical weights (confirmed by comparing tensors before/after)
while giving Keras a freshly-connected graph with none of the reload
quirks. If you ever see Grad-CAM silently produce a blank or uniform
heatmap with no error, this class of bug is the first thing to suspect.

## Preprocessing contract

`model_def.preprocess_image_file()`: resize directly to 224×224 (no
crop — see below), convert BGR→RGB, scale to [0,1] only — **no ImageNet
mean/std normalization**. This is a deliberate exact match to
`Retinex.ipynb`'s `preprocess_image`/`load_image` functions (cells
39/43/48/52/53), which all do `tf.cast(image, tf.float32) / 255.0` and
nothing else. **The model receives the original image, not the
CLAHE-enhanced one.** This matters: if you train on one preprocessing
pipeline and infer with another, sensitivity silently collapses — it's the
single most common way a plugged-in model quietly stops working.
`scripts/train.py` uses the identical normalization, so this contract is
enforced by construction, not just by convention. If your real trained
model was fit with different preprocessing (e.g. the Ben Graham
Gaussian-blur-subtraction trick common in APTOS-winning solutions), change
`_preprocess()` in `ml_model.py` and `make_dataset()` in `train.py`
together — never one without the other.

## Grad-CAM (`ml_model._grad_cam`, `model_def.build_grad_cam_model`)

Real implementation using `tf.GradientTape`, not a placeholder: gradients
of the predicted class's logit with respect to the auto-detected last
Conv2D layer's activations (see the Architecture section above — there's
no layer literally named "last_conv" in the current architecture, since it
matches the notebook's unnamed layers exactly), global-average-pooled into
per-channel weights, applied back onto the activation map, ReLU'd and
normalized. This is standard Grad-CAM (Selvaraju et al. 2017).

The sub-model that exposes those intermediate activations to the gradient
tape is built by `model_def.build_grad_cam_model()`, not a plain
`tf.keras.Model(inputs=..., outputs=[layer.output, model.output])` — see
the Architecture section above for why the plain version silently breaks
(produces `None` gradients) for this specific reloaded-Sequential-model
case, and how the fix works. If Grad-CAM ever silently produces a blank
or uniform heatmap with no exception raised, check `grads is None` first;
it's a much easier bug to miss than a crash.

## The consistency check

`ml_model._consistency_check()` compares the model's grade against two
independent signals: a crude "lesion floor" (any hemorrhage or significant
exudate area implies at least level 2; any microaneurysm implies at least
level 1 — see `lesions.rule_based_level_floor()`), and what fraction of
detected lesion points fall inside the Grad-CAM's hot region (>0.5
normalized activation). Either mismatch sets `evidence.consistent = false`
and surfaces a "⚠ review carefully" flag in the UI. This is a heuristic
safety net, not a substitute for the model being right — its purpose is to
catch cases where the model and the visible evidence disagree, which is
exactly when a human reviewer's attention is most valuable.

## Non-square input images: distortion is intentional, not a bug

Fundus cameras in the field produce wildly different resolutions and
aspect ratios, and APTOS 2019 itself is no exception — checked directly
against the dataset (see cell 24 of the notebook): image sizes from
1050×1050 up through 2848×4288, a dozen distinct aspect ratios in the
training set alone. `Retinex.ipynb` resizes every image straight to
224×224 with no cropping step, which **anisotropically stretches the
retinal circle into an ellipse**, differently depending on each source
image's original aspect ratio.

That's normally something to fix — an earlier version of this pipeline
did exactly that, with `processing.crop_to_square_array()` cropping to a
square field-of-view bounding box before resizing, so the resize became a
distortion-free uniform scale. **That fix has been deliberately reverted**
for the currently-deployed checkpoint, because the checkpoint was trained
*without* that crop: feeding it a cropped, undistorted image now would be
feeding it a different geometry than it learned on, which would silently
produce meaningless predictions — a model can only be evaluated fairly
using the same preprocessing it learned under, even when that
preprocessing has a known flaw.

`processing.crop_to_square_array()` and `standardize_frame()` still exist,
fully implemented and tested, purely unused by the default pipeline. **If
you add proper square-cropping to the notebook's preprocessing on a future
retrain,** re-enable the crop by calling `processing.crop_to_square_array()`
inside `model_def.preprocess_image_file()` again (it was removed from
there specifically) — and add the equivalent crop step to the notebook's
own `preprocess_image`/`load_image` functions in the same change, or
you'll reintroduce exactly this train/inference mismatch in the other
direction.

This is centralized in **`model_def.preprocess_image_file()`** — the
single function `ml_model.py` (inference), `scripts/train.py`,
`scripts/calibrate.py`, and `scripts/evaluate.py` all call. One shared
function, used everywhere, means a future change to preprocessing (like
re-adding the crop) only has to happen in one place — an earlier version
of this pipeline had inference and calibration each computing
preprocessing slightly differently, which silently broke things (see the
Grad-CAM section above for a similar class of bug), and that's exactly
the failure mode this centralization exists to prevent.

`main.py` no longer runs any framing/cropping step before enhancement,
lesion detection, or model inference — all three now operate on the same
raw uploaded image, at its original resolution and aspect ratio. This is
also why lesion points and the Grad-CAM heatmap can still be compared
directly in `_consistency_check()`: with no crop happening anywhere,
there's no coordinate offset between them to begin with.

## Making it real

**Progress so far: steps 1–2 done** (via the notebook, not this project's
own scripts — see step 2 below). Steps 3–4 (calibrate, evaluate) haven't
run yet — see the callout at the top of this document for exact commands.

1. ~~**Get labeled data.**~~ Done — trained on APTOS 2019. Not yet done:
   IDRiD (useful for checking `lesions.py` against its pixel-level lesion
   masks) and Messidor-2, which is reserved as the held-out test set for
   step 4 — do not train or calibrate on it.
2. ~~**Train:** `python scripts/train.py --data_dir data/ --epochs 15`.~~
   Done — but via `Retinex.ipynb` directly, not this script. `model_def.
   build_model()` has been kept in sync with the notebook's architecture
   (see Architecture above) specifically so that running `scripts/train.py`
   from here on would reproduce it, but the actual weights currently
   loaded came from the notebook. Class weights in the notebook were not
   computed/balanced against class imbalance (checked: no `class_weight`
   passed to `.fit()`) — `scripts/train.py` does this automatically if you
   retrain through it instead.
3. **Calibrate (not yet run):** `python scripts/calibrate.py --data_dir
   data/ --target_sensitivity 0.92`. Fits a temperature (minimizes
   validation negative log-likelihood) and a referable-decision threshold
   on `P(level≥2)` that hits your sensitivity target — this is what lets
   you actually hit "sensitivity ≥ 90%" rather than hoping argmax happens
   to get there. Writes `backend/config.json`, overwriting the current
   placeholder `temperature: 1.0, referable_threshold: 0.5`.
4. **Evaluate once (not yet run):** `python scripts/evaluate.py
   --data_dir test_data/` on a held-out set never used in steps 2–3
   (Messidor-2). Writes `backend/metrics.json`, which `/api/metrics` and
   the results view read from. Never re-tune based on what this script
   reports — that's how test sets stop meaning anything. **This is the
   step that actually produces the brief's sensitivity/specificity
   numbers — nothing before it does.**
5. **Restart the backend.** `init_model()` picks up the new checkpoint and
   config automatically on the next startup.

## Known limitations of the eventual real model

- 224×224 input downsamples away genuinely sub-pixel features; true
  microaneurysm-level detection (a brief requirement) needs a
  segmentation-specific architecture or higher input resolution, which is
  a real accuracy/compute trade-off worth revisiting once you have a
  working baseline.
- No neovascularization-specific detector — proliferative DR (level 4) is
  graded by the same classifier as everything else, with no dedicated
  vessel-growth pathway. Flagged in `limitations_and_roadmap.md`.
- Calibration and thresholding are only as good as the validation set they
  were fit on; recalibrate whenever the deployment population changes
  (e.g. moving from one Indian state's camera fleet to another's).
