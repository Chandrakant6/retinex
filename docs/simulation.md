# District Workflow Simulation

## What it models

A telemedicine DR screening program has three sequential stages, each with
a maximum throughput ("capacity") and a queue that builds up when incoming
work exceeds that capacity:

```
patients at camera sites
        │  images_per_patient × patients/site/day
        ▼
  ┌─────────────┐   capacity = bandwidth / image_size
  │ Upload queue │──────────────────────────────────▶  uploaded images
  └─────────────┘
        │
        ▼
  ┌─────────────┐   capacity = 3600 / ai_seconds_per_image
  │  AI queue    │──────────────────────────────────▶  graded images
  └─────────────┘
        │  only review_fraction of graded images need a human
        ▼
  ┌──────────────┐  capacity = num_reviewers × 3600 / review_seconds
  │ Review queue │──────────────────────────────────▶  reviewed images
  └──────────────┘
```

`backend/simulation.py` runs this hour-by-hour over a simulated period
(default 30 days × 10 working hours), tracking each queue's length. Outputs:

- **`capacity_per_hour`** — the theoretical max throughput of each stage,
  and how many images/hour are actually arriving. Whichever stage has the
  smallest capacity relative to demand is the **bottleneck**.
- **`summary.annual_patients_capacity`** — sites × patients/site/day × 250
  working days/year. Compare against the brief's 100,000+/year target.
- **`summary.max_review_backlog_images`** and **`backlog_clear_time_hours`**
  — if reviewers can't keep up, the queue grows without bound over the
  simulated period; this tells you how bad it gets and how long it would
  take to clear if arrivals stopped.
- **`summary.reviewer_utilization_pct`** — how close to fully loaded your
  reviewers are. Useful for finding the smallest reviewer count that
  doesn't create an ever-growing backlog.

## Why Python instead of Simulink

This MVP was built without MATLAB/Simulink access. Rather than skip the
requirement, the same queueing logic was implemented directly and
transparently in Python — which has the advantage of being immediately
testable and versioned alongside the rest of the code, but the
disadvantage of not being Simulink.

**Every parameter here maps directly onto a standard Simulink block**, so
porting is mechanical, not a redesign:

| This model | Simulink equivalent |
|---|---|
| Hourly loop with a running queue length | A `Discrete-Time Integrator` or a `Queue` block from Simulink's Communications/DES support, driven by a fixed-step clock |
| `min(queue, capacity)` per stage | A saturation/rate-limited `Server` block |
| Three sequential stages | Three `Server`+`Queue` block pairs in series |
| `review_fraction` split | A `Switch` or probability-gated `Demux` routing a fraction of tokens onward |
| Sweeping `num_reviewers` | A `Simulink Design Optimization` parameter sweep, or a simple `for` loop over `sim("model", "num_reviewers", n)` calls |

If/when MATLAB access is available, the fastest path is: build the three
`Server`/`Queue` pairs in series in Simulink using these same default
parameter values, verify the steady-state queue lengths match this
script's output for a few parameter combinations (a good regression test),
then use Simulink's built-in optimization tools for the resource-allocation
sweep the brief asks for.

## Using the planning dashboard

The frontend's "District Planning" tab exposes every input as a slider and
re-runs the simulation on every change (`POST /api/simulate`). The
recommended way to use it in a demo: set patient volume to your target
(sliders default to a 100,000/year configuration — 20 sites × 20
patients/day × 250 days), then reduce `num_reviewers` until the "Time to
clear peak review backlog" stat turns red, and increase it back one step —
that's your minimum viable reviewer count for that patient volume. Toggle
`review_fraction` down to near-zero to see the "AI triage off" baseline (as
if every image needed full manual review) versus a realistic triage
fraction, which is the clearest way to demonstrate AI's throughput benefit
to a district health officer.

## Limitations of the current model

- Deterministic (no randomness/variance in arrival times, processing
  times, or reviewer availability) — a real system would want Poisson
  arrivals and reviewer shift patterns; this is a reasonable next
  refinement, whether in Python or Simulink.
- No modeling of network outages, camera downtime, or multi-day patient
  no-shows, which matter a lot in real rural connectivity conditions.
- `review_fraction` is a single global constant; in reality it should
  derive directly from the model's own referable + "flagged inconsistent"
  rate measured in `validation.md`, not be set independently.
