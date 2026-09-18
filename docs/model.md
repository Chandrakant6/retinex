# The Model

## Current status: trained on APTOS 2019, not yet calibrated or evaluated

**Read this first.** `backend/checkpoints/model.keras` now holds weights
trained on the APTOS 2019 dataset (architecture unchanged from
`model_def.py` — see "Making it real" below for exactly which step this
corresponds to). This is real progress, but two things are still true:

- **Confidence scores are uncalibrated.** `config.json` still has
  `temperature: 1.0` — the raw softmax output, not adjusted to match actual
  accuracy. A model can be well-trained and still say "91% confident" when
  it's right 70% of the time; temperature scaling is what fixes that, and
  it hasn't run yet.
- **The referable decision threshold is still the untuned default (0.5).**
  The brief's target — >90% sensitivity, >85% specificity for referable DR
  — is tuned for by `scripts/calibrate.py` picking a `P(level≥2)` cutoff
  against a validation set. Until that runs, the app is deciding
  "referable" by whichever class got the highest raw probability, which is
  not the same thing and will not hit the sensitivity target reliably.
- **No held-out evaluation has been run.** Training and (eventually)
  calibration both used APTOS 2019. Nothing has been measured on Messidor-2
  or any dataset the model hasn't seen, so there are no sensitivity/
  specificity/AUC numbers yet — real or otherwise. Do not report the
  brief's target metrics as met until `scripts/evaluate.py` has run against
  a genuinely held-out set.

**The immediate next steps, in order:**
```bash
cd backend
python scripts/calibrate.py --data_dir data/ --target_sensitivity 0.92
python scripts/evaluate.py --data_dir test_data/   # Messidor-2, never touched during training
```
See `doc/validation.md` for what each of these produces and how to report
it honestly.

Everything below describes the architecture as designed and the full path
from here to a validated model.

## Architecture (`backend/model_def.py`)

A small custom CNN, not a pretrained backbone:

```
Input (224×224×3)
→ Conv(32) → BN → MaxPool
→ Conv(64) → BN → MaxPool
→ Conv(128) → BN → MaxPool
→ Conv(256, name="last_conv") → BN         ← Grad-CAM reads this layer
→ GlobalAveragePooling → Dropout(0.3)
→ Dense(128, relu) → Dropout(0.2)
→ Dense(5, name="icdr_logits")              ← pre-softmax, used for calibration
→ Softmax → 5-way ICDR probability
```

~424K parameters, ~1.6MB. Two design choices worth explaining:

**Why not a pretrained backbone (ResNet/EfficientNet)?** This build
environment has no route to download ImageNet weights (no access to
`storage.googleapis.com` or similar). More importantly: a compact model
that runs fast on a CPU at a rural primary health centre — where a GPU is
unlikely — matters more for this use case than squeezing out another point
of accuracy from a huge backbone. If you have real training compute,
swapping in a bigger backbone is a localized change to `model_def.py`;
nothing else in the pipeline needs to know.

**Why a separate named logits layer?** Grad-CAM and temperature-scaling
calibration both need pre-softmax logits. The straightforward-looking
shortcut — grabbing `model.layers[-1].input` — actually returns the
*input* to the final Dense layer (the 128-d pooled features), not its
logits, which silently produces nonsense. This was an actual bug caught
during development (see the code history / commit if using git) by
sanity-checking a raw prediction and finding 128-way "probabilities"
instead of 5. Fixed by giving the logits their own named layer
(`icdr_logits`) so inference code reads them directly and unambiguously.
Worth knowing about if you modify the architecture: always give yourself a
named handle on any intermediate tensor you'll need to reach into later.

## Preprocessing contract

`ml_model._preprocess()`: resize to 224×224, convert BGR→RGB, scale to
[0,1], normalize with ImageNet mean/std (`[0.485,0.456,0.406]` /
`[0.229,0.224,0.225]`). **The model receives the original image, not the
CLAHE-enhanced one.** This matters: if you train on one preprocessing
pipeline and infer with another, sensitivity silently collapses — it's the
single most common way a plugged-in model quietly stops working.
`scripts/train.py` uses the identical normalization, so this contract is
enforced by construction, not just by convention. If your real trained
model was fit with different preprocessing (e.g. the Ben Graham
Gaussian-blur-subtraction trick common in APTOS-winning solutions), change
`_preprocess()` in `ml_model.py` and `make_dataset()` in `train.py`
together — never one without the other.

## Grad-CAM (`ml_model._grad_cam`)

Real implementation using `tf.GradientTape`, not a placeholder: gradients
of the predicted class's logit with respect to the `last_conv` layer's
activations, global-average-pooled into per-channel weights, applied back
onto the activation map, ReLU'd and normalized. This is standard Grad-CAM
(Selvaraju et al. 2017) and works correctly regardless of whether the
underlying weights are trained — you're welcome to verify this yourself by
inspecting `backend/artifacts/*/gradcam.png` after screening an image;
right now, with untrained weights, the heatmap reflects whatever the random
weights respond to, which is why it won't look clinically sensible yet.

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

## Handling varying input resolutions and aspect ratios

Fundus cameras in the field produce wildly different resolutions and aspect
ratios — a 4:3 phone photo, a 16:9 crop, different manufacturers' default
framing, different amounts of black border around the circular retina.
**Naively resizing a non-square image straight to 224×224 distorts the
retinal circle into an ellipse**, differently depending on each image's
original shape — a real accuracy risk, not a cosmetic one, since it changes
vessel/lesion geometry inconsistently across images.

The fix, in `processing.crop_to_square_array()`: crop to a square bounding
box around the circular field of view (reusing the same brightness mask
`assess_quality()` computes) before any resize happens, padding to an exact
square if the crop is clipped by the frame edge. Resizing that square down
to 224×224 is then a uniform scale with no distortion, regardless of the
original resolution or aspect ratio.

This is centralized in **`model_def.preprocess_image_file()`** — the single
function `ml_model.py` (inference), `scripts/train.py`, `scripts/
calibrate.py`, and `scripts/evaluate.py` all call. This matters beyond
just correctness: an earlier version of this pipeline had inference and
calibration each computing preprocessing slightly differently, which
silently broke things (see "why a separate named logits layer" above for a
similar class of bug). One shared function, used everywhere, closes off
that entire failure mode — if you ever change how images are preprocessed,
there is exactly one place to change it.

`main.py` additionally runs `processing.standardize_frame()` (the file-based
wrapper around the same crop) once per screening request, producing
`framed.png`, and derives the enhanced image, the model input, and the
lesion-detection input all from that same square frame. This is also why
lesion points and the Grad-CAM heatmap can be compared directly in
`_consistency_check()` — they're always expressed in the same square
coordinate space, just at different resolutions, so converting between
them is a single ratio rather than something needing a crop offset too.



## Making it real

**Progress so far: steps 1–2 done.** Trained on APTOS 2019 with the
architecture unchanged. Steps 3–4 (calibrate, evaluate) haven't run yet —
see the callout at the top of this document for exact commands.

1. ~~**Get labeled data.**~~ Done — trained on APTOS 2019. Not yet done:
   IDRiD (useful for checking `lesions.py` against its pixel-level lesion
   masks) and Messidor-2, which is reserved as the held-out test set for
   step 4 — do not train or calibrate on it.
2. ~~**Train:** `python scripts/train.py --data_dir data/ --epochs 15`.~~
   Done, on APTOS 2019. Class weights were computed automatically (public
   DR datasets are imbalanced, typically ~35/25/25/10/5 across levels 0–4)
   — worth confirming the training run's logged class weights look
   reasonable for your split.
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
