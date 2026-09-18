# Architecture

## System diagram

```
                         ┌─────────────────────────┐
   phone / fundus  ───▶  │   React frontend (Vite) │
   camera photo          │   Screen · Worklist ·    │
                         │   District Planning       │
                         └───────────┬──────────────┘
                                     │ HTTP (JSON + multipart)
                                     ▼
                         ┌─────────────────────────┐
                         │   FastAPI backend        │
                         │   main.py                │
                         └───┬──────────┬───────┬───┘
                             │          │       │
                 ┌───────────▼──┐  ┌────▼───┐ ┌─▼────────────┐
                 │ processing.py │  │lesions │ │ ml_model.py  │
                 │ quality gate  │  │ .py    │ │ TensorFlow   │
                 │ + enhancement │  │classic │ │ CNN + Grad-  │
                 │ (OpenCV)      │  │lesion  │ │ CAM          │
                 └───────────────┘  │detect  │ └──────────────┘
                                    └────────┘
                             │
                 ┌───────────▼──────────────┐
                 │ simulation.py             │
                 │ district workflow model   │
                 └───────────────────────────┘
```

## Why this shape

**Frontend and backend are fully decoupled** over a JSON/multipart HTTP API
(`doc/api.md`). Either side can be rebuilt independently — this was
deliberate given the original team split (web dev vs. AI dev): the API
contract in `ml_model.py`'s docstring is the seam between "the model" and
"everything else," and nothing outside that file needed to change as the
model went from mock to trained TensorFlow.

**Every external dependency degrades gracefully.** `processing.py` doesn't
need MATLAB — it's pure OpenCV. `ml_model.py` falls back to a deterministic
mock predictor if TensorFlow or the model checkpoint is missing, so the
frontend and API always work even mid-development or if a checkpoint fails
to load. This mirrors the original proof-of-concept's MATLAB→OpenCV
fallback pattern, extended to the ML layer.

**In-memory state only.** `main.py` keeps cases in a Python dict, not a
database. Fine for a demo/single-process MVP; the first production task is
swapping this for real storage (see `limitations_and_roadmap.md`).

## Mapping to the problem brief

| Brief requirement | Implementation | File(s) |
|---|---|---|
| 1. Quality assessment & enhancement | 3-tier (good/borderline/reject) OpenCV quality gate; CLAHE + denoise enhancement for borderline images only | `backend/processing.py` |
| 2. Retinal structure segmentation | Classical optic disc localization, microaneurysm/hemorrhage/exudate detection via morphological ops | `backend/lesions.py` |
| 3. DR severity grading (ICDR 0–4) | TensorFlow CNN, calibrated via temperature scaling, referable (level≥2) decision via a tuned threshold rather than raw argmax | `backend/model_def.py`, `ml_model.py`, `scripts/calibrate.py` |
| 4. Explainability | Grad-CAM (`tf.GradientTape`, real gradients on real conv activations) + lesion evidence + model/lesion consistency check + printable HTML report | `ml_model.py`, `lesions.py`, `main.py` (`/api/report`) |
| 5. Simulink workflow simulation | Python discrete-time queue simulation (upload → AI → review), parameterized identically to how a Simulink model would be block-for-block | `backend/simulation.py`, `frontend/src/PlanningPage.jsx` |

Segmentation and simulation are simplified relative to the full brief
(classical CV instead of a learned segmentation network; Python instead of
actual Simulink) — see `limitations_and_roadmap.md` for the reasoning and
the upgrade path.

## Data flow for one screening request

1. Frontend uploads the image as multipart form data to `POST /api/screen`.
2. Backend saves it, runs `processing.assess_quality()`.
3. If rejected: return immediately with reasons + recapture guidance. No
   grading happens on ungradeable images — this matters for the brief's
   accuracy claims, since garbage input would otherwise silently lower
   measured sensitivity/specificity.
4. If borderline: `processing.enhance_image()` (CLAHE + denoise) runs
   before grading. Good images are graded as captured, to avoid distorting
   an already-clean photo.
5. `ml_model.predict()` runs the CNN on the **original** image (not the
   enhanced one — see `model.md` for why), produces calibrated
   probabilities, Grad-CAM heatmap, and calls `lesions.detect()` on the
   enhanced image for evidence.
6. A consistency check compares the model's grade against a crude
   lesion-count floor and against how much of the detected lesions fall
   inside the Grad-CAM hot region — this is the signal that becomes the
   "⚠ review carefully" flag.
7. Response returns to the frontend with image URLs, grade, evidence, and
   engine info (`tensorflow` or `mock`).
8. Clinician reviews in `ScreenPage`, decision posted to `POST /api/review`,
   which also updates running session stats (average review time, % under
   30 seconds, override rate) — this is how the "<30s review" claim gets
   measured rather than asserted.
