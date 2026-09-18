# API Reference

Base URL: `http://localhost:8000` (proxied to same-origin `/api` by the
frontend dev server). All responses are JSON unless noted.

---

## `GET /api/health`

```json
{ "status": "ok", "engine": "tensorflow" }
```
`engine` is `"tensorflow"` if a real model checkpoint loaded, `"mock"`
otherwise.

---

## `POST /api/screen`

Multipart form upload, field name `file` (image/jpeg or image/png).

**Rejected (quality gate failed):**
```json
{
  "id": "scr_a424224f",
  "status": "rejected",
  "created_at": "2026-09-18T04:12:09Z",
  "quality": {
    "tier": "reject",
    "gradable": false,
    "score": 0.0,
    "components": { "focus": 0.0, "illumination": 0.0, "field_of_view": 0.0 },
    "reasons": ["out_of_focus", "poor_illumination"],
    "guidance": "Please recapture: out of focus, poor illumination."
  },
  "filename": "photo.jpg"
}
```

**Complete:**
```json
{
  "id": "scr_a424224f",
  "status": "complete",
  "created_at": "2026-09-18T04:12:09Z",
  "processing_time_sec": 0.29,
  "quality": { "tier": "good", "gradable": true, "score": 0.96, "components": {...}, "reasons": [], "guidance": null },
  "grading": {
    "icdr_level": 2,
    "icdr_label": "Moderate NPDR",
    "referable": true,
    "referable_score": 0.81,
    "confidence": 0.74,
    "probabilities": [0.05, 0.14, 0.62, 0.15, 0.04],
    "recommendation": "Refer to ophthalmologist within 1 month"
  },
  "evidence": {
    "microaneurysm_count": 7,
    "hemorrhage_count": 3,
    "exudate_area_pct": 1.2,
    "cam_lesion_overlap_pct": 80.0,
    "consistent": true,
    "notes": []
  },
  "images": {
    "original": "/artifacts/scr_a424224f/original.png",
    "enhanced": "/artifacts/scr_a424224f/enhanced.png",
    "gradcam": "/artifacts/scr_a424224f/gradcam.png",
    "lesions": "/artifacts/scr_a424224f/lesions.png"
  },
  "engine": "tensorflow",
  "review": null
}
```

Quality tiers: `good` (graded as captured) → `borderline` (enhanced, then
graded) → `reject` (no grading, recapture guidance returned).

---

## `GET /api/cases`

Returns the in-memory worklist, ordered so referable and inconsistent
unreviewed cases sort first, then other unreviewed cases, then already-
reviewed/rejected cases.

```json
{ "cases": [ /* same shape as a /api/screen response, plus "review" */ ] }
```

## `GET /api/cases/{id}`

Single case, same shape. `404` if not found.

---

## `POST /api/review`

```json
{ "id": "scr_a424224f", "decision": "accept", "override_level": null, "review_time_sec": 18.4 }
```
`decision` is `"accept"` or `"override"` (with `override_level` 0–4 set).

```json
{
  "ok": true,
  "session_stats": {
    "reviewed": 12,
    "avg_review_time_sec": 22.3,
    "override_rate_pct": 8.3,
    "under_30s_pct": 91.7
  }
}
```
`session_stats` accumulates across the whole backend process — this is what
powers the "reviewed in under 30 seconds" claim: it's measured live from
real reviewer interactions, not asserted.

---

## `GET /api/report/{id}`

Returns an HTML page (not JSON) — a printable single-case report: images,
grade, evidence, recommendation, reviewer sign-off if reviewed. Use the
browser's Print → Save as PDF for a PDF export; no PDF library is used.
`400` if the case was rejected at the quality gate (nothing to report on).

---

## `GET /api/metrics`

```json
{ "available": false, "message": "Run backend/scripts/evaluate.py against a labeled test set first." }
```
or, after running `scripts/evaluate.py`:
```json
{
  "available": true,
  "n_test_images": 400,
  "config_used": { "temperature": 1.4, "referable_threshold": 0.42 },
  "comparison": {
    "A_model_only": { "tp": .., "fn": .., "tn": .., "fp": .., "sensitivity": .., "specificity": .. },
    "B_plus_quality_gate": {...},
    "C_plus_lesion_safety_net": {...}
  },
  "headline": {
    "sensitivity": 0.91, "sensitivity_95ci": [0.87, 0.94],
    "specificity": 0.86, "specificity_95ci": [0.82, 0.90],
    "meets_target": true
  }
}
```

---

## `POST /api/simulate`

Body (all fields optional, defaults shown):
```json
{
  "num_sites": 20,
  "patients_per_site_per_day": 20,
  "images_per_patient": 2,
  "image_size_mb": 2.5,
  "upload_bandwidth_mbps": 5.0,
  "ai_seconds_per_image": 2.0,
  "review_fraction": 0.35,
  "review_seconds": 25.0,
  "num_reviewers": 3,
  "sim_days": 30
}
```

Response: `inputs` (echoed), `capacity_per_hour` (images/hour each stage
can sustain), `summary` (annual patient capacity, peak backlog, backlog
clear time, reviewer utilization, current bottleneck), and `series`
(downsampled hourly queue lengths for charting). See `doc/simulation.md`
for how to interpret and extend this.
