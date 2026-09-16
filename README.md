# DR Screening — Prototype

Tested working: backend endpoints (health, screen-accept, screen-reject, review)
verified via FastAPI TestClient; frontend builds clean with `npm run build`.

## Run it

**Backend** (needs Python 3.10+):
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
On startup it tries to start a MATLAB engine. If MATLAB isn't installed, you'll
see `[matlab] unavailable (...); using OpenCV fallback` and the app runs
identically — every response includes `"engine": {...}` telling you which
path actually ran, so you always know what powered a given result.

**Frontend** (needs Node 18+):
```bash
cd frontend
npm install
npm run dev
```
Opens on `http://localhost:5173`, proxies `/api` and `/artifacts` to the
backend on port 8000 (see `vite.config.js`).

**MATLAB (optional):** install the MATLAB Engine API for Python
(`matlabroot/extern/engines/python` → `python setup.py install`), then
restart the backend. `matlab_src/assess_quality.m` and `matlab_src/enhance_image.m`
match the exact output contract `backend/processing.py` expects — test them
standalone in MATLAB first (`assess_quality('/path/to/image.jpg')`) before
relying on the Python bridge.

**Hard rule:** if MATLAB engine setup isn't working within 2 hours, stop.
The app runs correctly without it. Demo the `.m` files directly in MATLAB
Desktop if you want to show MATLAB usage live.

## Where the ML model plugs in

**`backend/ml_integration.py`** is the only file the AI engineer needs to touch.
It currently returns a deterministic mock (same image → same fake grade, so
demo/dev is repeatable). The docstring at the top of that file has the exact
input/output contract and a full sketch of the real PyTorch + Grad-CAM
implementation. Swap the body of `predict()`, keep the return shape, and
nothing in `main.py`, `processing.py`, or the frontend needs to change.

If the real model saves a Grad-CAM overlay PNG, save it into the same
directory as the enhanced image was written to (i.e. next to
`enhanced.png`) — `main.py` automatically picks it up and serves it as the
`gradcam` tab in the UI.

## API contract (frozen — don't change without syncing all three of you)

`POST /api/screen` — multipart `file` → quality check → enhance → grade.
Returns `status: "rejected"` (with reasons + guidance) or `status: "complete"`
(with grading, image URLs, engine info). See `main.py` for exact shape.

`POST /api/review` — `{id, decision, override_level, review_time_sec}` →
running session stats (count, avg review time, override rate). Powers the
live "avg review time" counter that evidences the <30s review claim on demo day.

## What's deliberately not here

No database (in-memory only), no auth, no PDF export, no pixel-level lesion
segmentation, no async job queue. Synchronous request/response end to end —
one call in, one full result out. This is a prototype; the full architecture
doc (if you have it from earlier planning) has the production roadmap.
