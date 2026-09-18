# Retinex — Documentation

Explainable AI screening pipeline for diabetic retinopathy (DR), built as a
one-week hackathon MVP against the brief in the project root.

This directory documents what was built, why it was built that way, and
what is left to do before it could touch a real patient. Read in this
order if you're new to the project:

1. **[architecture.md](architecture.md)** — how the pieces fit together, and
   how each of the brief's 5 requirements maps onto actual code.
2. **[setup.md](setup.md)** — how to run it, from zero.
3. **[api.md](api.md)** — every endpoint, request/response shapes.
4. **[model.md](model.md)** — the DL model: architecture, training,
   calibration, Grad-CAM, and — importantly — its current status (trained,
   not yet calibrated or evaluated) and what's needed to finish validating it.
5. **[validation.md](validation.md)** — how to measure sensitivity/
   specificity against the brief's targets, and the three-way comparison
   the brief asks for (single technique vs. integrated pipeline).
6. **[simulation.md](simulation.md)** — the district workflow model,
   its parameters, and how it maps to a future Simulink implementation.
7. **[limitations_and_roadmap.md](limitations_and_roadmap.md)** — everything
   this MVP deliberately does not do yet, and in what order to add it.

## One-paragraph summary

A fundus image is uploaded, checked for gradability (focus/illumination/
field of view), enhanced if borderline, graded 0–4 on the ICDR scale by a
TensorFlow CNN, and explained via Grad-CAM plus classical lesion detection
that cross-checks the model's grade. A reviewing clinician sees all of this
in under 30 seconds and accepts or overrides. A separate planning dashboard
simulates district-level throughput (upload bandwidth → AI processing →
human review) to size a screening program for 100,000+ patients/year.

## Status note

**The model is trained (APTOS 2019) but not yet calibrated or evaluated.**
Confidence scores are still raw/uncalibrated (`temperature: 1.0` in
`config.json`), the referable-DR decision threshold is still the untuned
default (0.5, not tuned against a validation set), and no held-out
evaluation has been run — so there are no real sensitivity/specificity
numbers yet. The brief's >90% sensitivity / >85% specificity targets are
not yet measured, let alone met. Run `scripts/calibrate.py` then
`scripts/evaluate.py` before reporting any accuracy claim — see
[model.md](model.md) for exact commands and what each step fixes.
