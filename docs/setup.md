# Setup

## Requirements

- Python 3.10+
- Node 18+
- No GPU required (the shipped model is a small CPU-friendly CNN)

## 1. Backend

```bash
cd backend
pip install -r requirements.txt

# Only if checkpoints/model.keras doesn't exist yet (e.g. a fresh clone
# with no trained weights). If a checkpoint already exists — including a
# trained one — skip this; running it again would refuse by default, and
# --force would destroy trained weights with no undo:
python scripts/build_model.py

uvicorn main:app --reload --port 8000
```

On startup you should see:
```
[ml_model] TensorFlow model loaded from .../checkpoints/model.keras; config={...}
```

If TensorFlow or the checkpoint isn't available, you'll instead see:
```
[ml_model] TensorFlow model unavailable (...); using mock predictor
```
The app runs identically either way — every screening response includes
`"engine": "tensorflow" | "mock"` so you always know which one produced a
given result. This is intentional: the frontend and API should never be
blocked by a model/environment problem.

Check it's alive:
```bash
curl http://localhost:8000/api/health
# {"status":"ok","engine":"tensorflow"}
```

## 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173`, proxying `/api` and `/artifacts` to the
backend on port 8000 (see `frontend/vite.config.js`). Open that URL, drop in
a fundus image, and you should see quality assessment → grading →
Grad-CAM/lesion evidence → accept/override.

For a single deployable build:
```bash
npm run build   # outputs frontend/dist
```
Serve `frontend/dist` from any static file host, with `/api` and
`/artifacts` reverse-proxied to the FastAPI backend (nginx, Caddy, or
FastAPI's own `StaticFiles` mount work equally well for a field deployment).

## 3. Calibrate and evaluate (current next step)

**Status: trained on APTOS 2019; calibration and evaluation not yet run**
(see `doc/model.md`). Confidence scores are still raw and the referable
threshold is still the untuned default until this runs:

```bash
cd backend
python scripts/calibrate.py --data_dir data/ --target_sensitivity 0.92
python scripts/evaluate.py --data_dir test_data/   # held-out set, e.g. Messidor-2 — never used in training
```

Restart the backend afterwards to pick up the new `config.json`.

To retrain from scratch instead (a different dataset, more epochs, an
architecture change):
```bash
python scripts/train.py --data_dir data/ --epochs 15
```
then repeat the calibrate/evaluate steps above.

## Directory layout

```
dr-screening/
  backend/
    main.py              FastAPI app — all routes
    processing.py        OpenCV quality gate + enhancement
    lesions.py            classical lesion detection
    model_def.py          TensorFlow model architecture (shared by all scripts)
    ml_model.py            inference + Grad-CAM + mock fallback
    simulation.py          district workflow queue simulation
    config.json             temperature + referable threshold (written by calibrate.py)
    checkpoints/            model.keras lives here
    artifacts/               per-screening saved images (gitignored)
    scripts/
      build_model.py          creates the initial untrained checkpoint
      train.py                 fine-tune on a real dataset
      calibrate.py              temperature scaling + threshold tuning
      evaluate.py                held-out test evaluation + comparison table
    requirements.txt
  frontend/
    src/
      App.jsx                  nav shell
      ScreenPage.jsx             upload/grade/review UI
      WorklistPage.jsx            case queue
      PlanningPage.jsx             district simulation dashboard
      api.js                        backend client
      lib.jsx                        shared constants + chart
      styles.css
    package.json
    vite.config.js
  samples/                     small synthetic test images (not real patient data)
  doc/                          you are here
```
