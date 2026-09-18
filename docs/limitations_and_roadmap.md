# Limitations & Roadmap

Said plainly, up front, because a hackathon demo that hides its gaps is
less useful than one that names them — and the brief itself asks for
"clinical validation rigor," which starts with intellectual honesty about
what hasn't been validated yet.

## What's deliberately not here

- **Model trained on one dataset, not yet calibrated or evaluated.**
  `checkpoints/model.keras` is trained on APTOS 2019, but confidence
  scores are uncalibrated and the referable threshold is still the untuned
  default — see `model.md` for the two-command fix
  (`scripts/calibrate.py` then `scripts/evaluate.py`) and why skipping
  straight to evaluation would misrepresent the sensitivity target.
- **No database.** Cases live in an in-memory Python dict and are lost on
  backend restart. Fine for a demo; not fine for a real clinic.
- **No auth.** Anyone who can reach the API can screen images and see all
  cases. A real deployment needs at minimum per-clinic accounts and access
  control before it touches real patient data.
- **No real Simulink model** — a Python discrete-time simulation stands in,
  with a documented block-for-block porting path (`simulation.md`).
- **Classical, not learned, lesion segmentation.** `lesions.py` uses
  morphological image processing (top-hat/black-hat filters), not a
  trained segmentation network. It's good enough to give a reviewer
  quick supporting evidence, not good enough to be a diagnostic
  lesion-counting tool on its own.
- **No neovascularization detector.** Proliferative DR (level 4) is graded
  by the same single classifier as every other level — there's no
  dedicated pathway looking specifically for abnormal vessel growth, which
  the brief calls out by name.
- **No sub-pixel microaneurysm detection.** 224×224 input resolution and
  classical blob detection both work against genuinely tiny lesions; this
  needs a segmentation-specific architecture and likely higher input
  resolution.
- **No PDF export library** — the HTML report relies on the browser's
  Print → Save as PDF, which works fine for a demo but isn't a
  programmatic PDF pipeline.
- **Synchronous, single-request processing** — no async job queue, so a
  slow model or a burst of uploads will queue requests at the HTTP level
  rather than in a proper background worker.

## Roadmap, roughly in priority order

1. ~~**Get a real dataset and train**~~ Done — trained on APTOS 2019.
2. **Calibrate + evaluate on a held-out set** — the immediate next step.
   Run `scripts/calibrate.py` (fixes uncalibrated confidence + the untuned
   referable threshold), then `scripts/evaluate.py` against Messidor-2 (a
   set the model has never seen). Report the sensitivity/specificity
   honestly, including if the >90%/>85% targets aren't met on the first
   pass (`validation.md`).
3. **Real Grad-CAM/lesion clinical review study** — even a small one with
   3–5 reviewers, done for real rather than skipped (`validation.md`).
4. **Persistent storage** — swap the in-memory dict for SQLite at minimum;
   Postgres if multi-site.
5. **Basic auth** — per-clinic login before any real image data flows
   through this.
6. **Learned lesion segmentation** — replace/augment `lesions.py` with a
   trained U-Net or similar on IDRiD's pixel-level masks, once the
   classifier itself is solid.
7. **Actual Simulink port** — once MATLAB access exists, port
   `simulation.py`'s logic block-for-block (mapping table in
   `simulation.md`) and use Simulink's optimization tooling for the
   resource-allocation sweep.
8. **Async processing + a real job queue** if/when request volume
   justifies it — not before, since it adds real complexity.

## What would make this genuinely deployable in rural India

Beyond the technical roadmap above: field testing with actual portable
fundus cameras (image quality characteristics differ meaningfully from
clinical-grade cameras used in APTOS/IDRiD/Messidor), an offline-first
mode for sites with unreliable connectivity (the frontend's system-font,
no-CDN-dependency choice is a first small step in this direction — see
`frontend/src/styles.css`), and a regulatory pathway conversation (this is
a screening aid, not a diagnostic device, and that distinction needs to be
enforced in the UI copy and the report footer, not just in this document).
