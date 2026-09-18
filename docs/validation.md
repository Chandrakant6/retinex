# Validation Plan

The brief's target: **>90% sensitivity, >85% specificity for referable DR
(ICDR level ≥ 2)**, validated against published benchmarks, with the
integrated pipeline shown to outperform any single technique alone.

This document describes how `scripts/evaluate.py` measures that.
**Current status: trained on APTOS 2019, but not yet calibrated or
evaluated** (see `model.md`) — so nothing below has actually been run
yet. Do not skip calibration and go straight to evaluation: the referable
decision is currently made with an untuned 0.5 threshold on raw softmax
output, which is not what "sensitivity ≥ 90%" means in the brief. Run
`scripts/calibrate.py` first, then `scripts/evaluate.py`, in that order.

## Datasets

| Dataset | Role |
|---|---|
| APTOS 2019 (Kaggle) | Train/validation — largest public labeled set |
| IDRiD | Validation + lesion-detection sanity check (has pixel-level masks) |
| Messidor-2 | **Held-out test set only** — never touched during training or calibration |

Using a third, untouched dataset as the final test set is what makes the
headline sensitivity/specificity numbers mean something: any dataset used
for both tuning and reporting will overstate performance.

## Metrics computed by `scripts/evaluate.py`

- **Referable sensitivity/specificity** with 95% confidence intervals
  (bootstrap resampling, 2000 iterations) — a point estimate alone from a
  few hundred test images isn't enough to claim ">90%" with confidence;
  the interval tells you whether the target is comfortably met or right at
  the edge of noise.
- **Confusion matrix** (tp/fn/tn/fp) for the referable (level≥2) decision.
- **The three-way comparison the brief explicitly asks for:**

  | Configuration | What it tests |
  |---|---|
  | A. Model alone | Raw classifier performance, no quality gate, no lesion cross-check |
  | B. + quality gate | Same model, but ungradeable images are excluded first (as they would be in production) |
  | C. + lesion safety net | B, plus: flag referable if EITHER the model OR the crude lesion-count floor says so |

  This directly produces the "integrated pipeline outperforms any single
  technique" evidence — report all three numbers side by side. If C
  doesn't win, that's still a valid and useful finding: report it as-is and
  explain why (e.g. the lesion floor may be too aggressive and hurt
  specificity more than it helps sensitivity — tune its thresholds in
  `lesions.rule_based_level_floor()` if so).

## Calibration quality

`scripts/calibrate.py` reports **Expected Calibration Error (ECE)** before
and after temperature scaling. A model can have good sensitivity/
specificity while still being poorly calibrated (e.g. always 99% confident)
— ECE is what tells a reviewing clinician whether "74% confidence" actually
means what it says. Report both numbers; a large ECE drop after calibration
is itself evidence the pipeline is doing something clinically sound, not
just accurate.

## Explainability validation ("clinically useful" claim)

The brief asks for Grad-CAM rated as clinically useful, not just present.
For a hackathon MVP, do this informally but honestly:

1. Recruit 3–5 people with some clinical/medical background (ideally
   ophthalmology residents; teammates or medical students are a reasonable
   fallback for a hackathon).
2. Have them review 15–20 real cases each through the actual `ScreenPage`
   UI — not slides, the real tool — using the accept/override workflow.
3. After each case, ask one question: *"Was the Grad-CAM/lesion evidence
   useful for this decision? (1–5)"*
4. Report the average rating, the spread, and any free-text comments
   verbatim. A small honest study beats an implied but unmeasured claim.

The same review sessions also produce your real numbers for the <30-second
review claim — `session_stats` from `/api/review` accumulates
`avg_review_time_sec` and `under_30s_pct` live, so you're reporting
measured behavior, not a target.

## What "validated against published benchmarks" means here

Report your Messidor-2 sensitivity/specificity/AUC next to published
numbers for models evaluated on the same or a comparable dataset (cite
papers using APTOS/IDRiD/Messidor-2 for referable DR detection). Be
explicit about differences in methodology (input resolution, class
definitions, whether a quality gate was applied) rather than presenting
raw numbers as directly comparable — reviewers will ask, and having the
caveat ready is more convincing than a bare number.
