# Retinex — Explainable AI for Diabetic Retinopathy Screening

A one-week hackathon MVP for the brief: automated, explainable DR screening
for rural primary health centres in India — quality-aware image intake,
ICDR 0–4 grading, Grad-CAM + lesion-evidence explainability, a sub-30-second
clinician review workflow, and a district-level throughput simulation.

**Stack:** React (Vite) frontend · FastAPI backend · TensorFlow (Keras) CNN.

```
cd backend  && pip install -r requirements.txt && python scripts/build_model.py && uvicorn main:app --reload
cd frontend && npm install && npm run dev
```

Then open `http://localhost:5173`.

**→ Full documentation, including an honest account of what is and isn't
validated yet, lives in [`doc/`](doc/README.md). Start there.**

## Quick orientation

```
backend/    FastAPI app, OpenCV quality gate, TensorFlow model, lesion
            detection, workflow simulation, and train/calibrate/evaluate
            scripts
frontend/   React app: Screen (upload → grade → review), Worklist,
            District Planning (simulation dashboard)
doc/        Architecture, API reference, model card, validation plan,
            simulation notes, setup guide, limitations & roadmap
samples/    Small synthetic test images (not real patient data) for
            exercising the reject/borderline/good quality paths
```

**Before you do anything else, read [`doc/README.md`](doc/README.md) —
in particular the honesty note about the shipped model checkpoint being
untrained.** The pipeline is complete and tested end-to-end; the model
inside it needs a real dataset and training run before its predictions
mean anything.
