import os
import shutil
import time
import uuid
from typing import Optional

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import processing
import ml_integration

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
os.makedirs(ARTIFACT_DIR, exist_ok=True)

app = FastAPI(title="DR Screening Prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/artifacts", StaticFiles(directory=ARTIFACT_DIR), name="artifacts")

_session_reviews: list["ReviewRequest"] = []


@app.on_event("startup")
def startup():
    processing.init_matlab()


@app.get("/api/health")
async def health():
    return {"status": "ok", "matlab": processing.USE_MATLAB}


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
    if not quality["gradable"]:
        return {
            "id": sid,
            "status": "rejected",
            "quality": quality,
        }

    enhanced_path = os.path.join(sdir, "enhanced.png")
    enh = processing.enhance_image(orig_path, enhanced_path)

    prediction = ml_integration.predict(enh["path"])

    images = {
        "original": f"/artifacts/{sid}/original.png",
        "enhanced": f"/artifacts/{sid}/enhanced.png",
        "gradcam": None,
    }
    if prediction.get("gradcam_path"):
        # normalize to a URL under /artifacts/{sid}/... if the model saved one
        gradcam_name = os.path.basename(prediction["gradcam_path"])
        images["gradcam"] = f"/artifacts/{sid}/{gradcam_name}"

    return {
        "id": sid,
        "status": "complete",
        "processing_time_sec": round(time.time() - start, 2),
        "quality": quality,
        "grading": {
            "icdr_level": prediction["icdr_level"],
            "icdr_label": prediction["icdr_label"],
            "referable": prediction["referable"],
            "confidence": prediction["confidence"],
            "probabilities": prediction["probabilities"],
        },
        "images": images,
        "engine": {"quality": quality.get("engine"), "enhance": enh.get("engine")},
    }


class ReviewRequest(BaseModel):
    id: str
    decision: str  # "accept" | "override"
    override_level: Optional[int] = None
    review_time_sec: float


@app.post("/api/review")
async def review(req: ReviewRequest):
    _session_reviews.append(req)
    n = len(_session_reviews)
    avg_time = round(sum(r.review_time_sec for r in _session_reviews) / n, 1)
    overrides = sum(1 for r in _session_reviews if r.decision == "override")
    return {
        "ok": True,
        "session_stats": {
            "reviewed": n,
            "avg_review_time_sec": avg_time,
            "override_rate_pct": round(overrides / n * 100, 1),
        },
    }
