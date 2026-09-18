import json
import os
import shutil
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import processing
import ml_model
import simulation

BACKEND_DIR = os.path.dirname(__file__)
ARTIFACT_DIR = os.path.join(BACKEND_DIR, "artifacts")
METRICS_PATH = os.path.join(BACKEND_DIR, "metrics.json")
os.makedirs(ARTIFACT_DIR, exist_ok=True)

app = FastAPI(title="DR Screening MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/artifacts", StaticFiles(directory=ARTIFACT_DIR), name="artifacts")

# In-memory store — fine for a single-process MVP demo, not for production.
_cases: dict[str, dict] = {}
_session_reviews: list[dict] = []


@app.on_event("startup")
def startup():
    ml_model.init_model()


@app.get("/api/health")
async def health():
    return {"status": "ok", "engine": "tensorflow" if ml_model.USE_TF else "mock"}


@app.post("/api/screen")
async def screen(file: UploadFile = File(...)):
    start = time.time()
    sid = "scr_" + uuid.uuid4().hex[:8]
    sdir = os.path.join(ARTIFACT_DIR, sid)
    os.makedirs(sdir, exist_ok=True)

    orig_path = os.path.join(sdir, "original.png")
    with open(orig_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    quality = processing.assess_quality(orig_path)

    if quality["tier"] == "reject":
        case = {
            "id": sid, "status": "rejected", "created_at": datetime.utcnow().isoformat(),
            "quality": quality, "filename": file.filename,
        }
        _cases[sid] = case
        return case

    # Standardize to a square crop around the retinal FOV BEFORE anything
    # else touches the image. This is what makes the model's resize-to-224
    # a distortion-free uniform scale regardless of the camera's original
    # resolution/aspect ratio, and keeps lesion points and the Grad-CAM
    # heatmap in the same coordinate space. See processing.standardize_frame.
    framed_path = os.path.join(sdir, "framed.png")
    processing.standardize_frame(orig_path, framed_path)

    # "good" images are graded as-is; "borderline" images are enhanced first.
    if quality["tier"] == "borderline":
        enhanced_path = os.path.join(sdir, "enhanced.png")
        processing.enhance_image(framed_path, enhanced_path)
    else:
        enhanced_path = os.path.join(sdir, "enhanced.png")
        shutil.copy(framed_path, enhanced_path)

    prediction = ml_model.predict(framed_path, enhanced_path, sdir)

    images = {
        "original": f"/artifacts/{sid}/original.png",
        "enhanced": f"/artifacts/{sid}/enhanced.png",
        "gradcam": f"/artifacts/{sid}/{os.path.basename(prediction['gradcam_path'])}",
        "lesions": f"/artifacts/{sid}/{os.path.basename(prediction['lesions_path'])}",
    }

    case = {
        "id": sid,
        "status": "complete",
        "created_at": datetime.utcnow().isoformat(),
        "filename": file.filename,
        "processing_time_sec": round(time.time() - start, 2),
        "quality": quality,
        "grading": {
            "icdr_level": prediction["icdr_level"],
            "icdr_label": prediction["icdr_label"],
            "referable": prediction["referable"],
            "referable_score": prediction["referable_score"],
            "confidence": prediction["confidence"],
            "probabilities": prediction["probabilities"],
            "recommendation": prediction["recommendation"],
        },
        "evidence": prediction["evidence"],
        "images": images,
        "engine": prediction["engine"],
        "review": None,
    }
    _cases[sid] = case
    return case


@app.get("/api/cases")
async def list_cases():
    """Worklist — most recent first, unreviewed + referable/inconsistent cases surfaced first."""
    cases = list(_cases.values())

    def priority(c):
        if c["status"] != "complete" or c.get("review"):
            return 2
        if c["grading"]["referable"] or not c["evidence"]["consistent"]:
            return 0
        return 1

    cases.sort(key=lambda c: (priority(c), c["created_at"]), reverse=False)
    return {"cases": cases}


@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    if case_id not in _cases:
        raise HTTPException(404, "case not found")
    return _cases[case_id]


class ReviewRequest(BaseModel):
    id: str
    decision: str  # "accept" | "override"
    override_level: Optional[int] = None
    review_time_sec: float


@app.post("/api/review")
async def review(req: ReviewRequest):
    if req.id not in _cases:
        raise HTTPException(404, "case not found")

    _cases[req.id]["review"] = {
        "decision": req.decision,
        "override_level": req.override_level,
        "review_time_sec": req.review_time_sec,
        "reviewed_at": datetime.utcnow().isoformat(),
    }
    _session_reviews.append(req.dict())

    n = len(_session_reviews)
    avg_time = round(sum(r["review_time_sec"] for r in _session_reviews) / n, 1)
    overrides = sum(1 for r in _session_reviews if r["decision"] == "override")
    under_30 = sum(1 for r in _session_reviews if r["review_time_sec"] <= 30)

    return {
        "ok": True,
        "session_stats": {
            "reviewed": n,
            "avg_review_time_sec": avg_time,
            "override_rate_pct": round(overrides / n * 100, 1),
            "under_30s_pct": round(under_30 / n * 100, 1),
        },
    }


@app.get("/api/report/{case_id}", response_class=HTMLResponse)
async def report(case_id: str):
    if case_id not in _cases:
        raise HTTPException(404, "case not found")
    c = _cases[case_id]
    if c["status"] != "complete":
        raise HTTPException(400, "case was rejected at quality check; no report to generate")

    g, ev, img = c["grading"], c["evidence"], c["images"]
    review_html = ""
    if c.get("review"):
        r = c["review"]
        final_level = r["override_level"] if r["decision"] == "override" and r["override_level"] is not None else g["icdr_level"]
        review_html = f"""<div class="box"><h3>Reviewer sign-off</h3>
            <p>Decision: <b>{r['decision']}</b> — final level: <b>{final_level}</b></p>
            <p>Review time: {r['review_time_sec']}s · {r['reviewed_at']} UTC</p></div>"""
    else:
        review_html = '<div class="box"><p><i>Not yet reviewed by a clinician.</i></p></div>'

    consistency_html = (
        f'<p style="color:#2e7d32">✓ AI grade is consistent with visible lesion evidence.</p>'
        if ev["consistent"] else
        f'<p style="color:#c62828">⚠ Lesion evidence and AI grade disagree — review carefully.</p>'
    )

    return f"""
    <html><head><title>DR Screening Report — {case_id}</title>
    <style>
        body {{ font-family: -apple-system, Arial, sans-serif; max-width: 900px; margin: 30px auto; color: #222; }}
        h1 {{ font-size: 20px; }} .box {{ border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 12px 0; }}
        img {{ max-width: 260px; border-radius: 6px; margin-right: 10px; }}
        .imgs {{ display: flex; flex-wrap: wrap; }}
        .grade {{ font-size: 22px; font-weight: bold; }}
        @media print {{ body {{ margin: 0; }} }}
    </style></head><body>
        <h1>Diabetic Retinopathy Screening Report</h1>
        <p>Case ID: {case_id} · Generated: {datetime.utcnow().isoformat()} UTC · Engine: {c['engine']}</p>
        <div class="box">
            <div class="grade">Level {g['icdr_level']} — {g['icdr_label']}</div>
            <p>{'🔴 Referable' if g['referable'] else '🟢 Not referable'} · Confidence: {g['confidence']*100:.0f}%
               · Referable score: {g['referable_score']*100:.0f}%</p>
            <p><b>Recommendation:</b> {g['recommendation']}</p>
        </div>
        <div class="box">
            <h3>Evidence</h3>
            <p>Microaneurysms: {ev['microaneurysm_count']} · Hemorrhages: {ev['hemorrhage_count']}
               · Exudate area: {ev['exudate_area_pct']}%</p>
            {consistency_html}
        </div>
        <div class="box">
            <h3>Images</h3>
            <div class="imgs">
                <img src="{img['original']}"><img src="{img['enhanced']}">
                <img src="{img['gradcam']}"><img src="{img['lesions']}">
            </div>
        </div>
        {review_html}
        <p style="color:#888; font-size:12px;">Prototype output — not an approved diagnostic device.
           Validation status: see /doc/validation.md in the project repository.</p>
    </body></html>
    """


@app.get("/api/metrics")
async def metrics():
    if not os.path.exists(METRICS_PATH):
        return {"available": False, "message": "Run backend/scripts/evaluate.py against a labeled test set first."}
    return {"available": True, **json.load(open(METRICS_PATH))}


class SimulateRequest(BaseModel):
    num_sites: int = 20
    patients_per_site_per_day: int = 20
    images_per_patient: int = 2
    image_size_mb: float = 2.5
    upload_bandwidth_mbps: float = 5.0
    ai_seconds_per_image: float = 2.0
    review_fraction: float = 0.35
    review_seconds: float = 25.0
    num_reviewers: int = 3
    sim_days: int = 30


@app.post("/api/simulate")
async def simulate(req: SimulateRequest):
    return simulation.run_simulation(**req.dict())
