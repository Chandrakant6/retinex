"""
Hour-by-hour discrete-time simulation of a district telemedicine screening
program: image acquisition -> upload -> AI processing -> human review queue.

Plain Python, not SimPy or Simulink — deliberately simple so it's easy to
reason about, and every parameter here maps directly onto a Simulink block
(queue -> Delay/Server pair) if this gets ported later. See doc/simulation.md.
"""

WORK_HOURS_PER_DAY = 10


def run_simulation(
    num_sites: int = 20,
    patients_per_site_per_day: int = 20,
    images_per_patient: int = 2,
    image_size_mb: float = 2.5,
    upload_bandwidth_mbps: float = 5.0,
    ai_seconds_per_image: float = 2.0,
    review_fraction: float = 0.35,   # fraction of graded images a human must review (referable + borderline + flagged)
    review_seconds: float = 25.0,
    num_reviewers: int = 3,
    sim_days: int = 30,
):
    """Returns hourly time series plus summary stats. All queues are simple
    FIFO counters measured in 'images'."""
    total_hours = sim_days * WORK_HOURS_PER_DAY
    images_per_hour_in = (num_sites * patients_per_site_per_day * images_per_patient) / WORK_HOURS_PER_DAY

    upload_capacity_per_hour = (upload_bandwidth_mbps * 3600) / (image_size_mb * 8)
    ai_capacity_per_hour = 3600 / ai_seconds_per_image
    review_capacity_per_hour = num_reviewers * (3600 / review_seconds)

    upload_queue = 0.0
    ai_queue = 0.0
    review_queue = 0.0

    series = []
    for hour in range(total_hours):
        upload_queue += images_per_hour_in
        uploaded = min(upload_queue, upload_capacity_per_hour)
        upload_queue -= uploaded

        ai_queue += uploaded
        processed = min(ai_queue, ai_capacity_per_hour)
        ai_queue -= processed

        review_queue += processed * review_fraction
        reviewed = min(review_queue, review_capacity_per_hour)
        review_queue -= reviewed

        series.append({
            "hour": hour,
            "day": hour // WORK_HOURS_PER_DAY,
            "upload_queue": round(upload_queue, 1),
            "ai_queue": round(ai_queue, 1),
            "review_queue": round(review_queue, 1),
        })

    max_review_backlog = max(p["review_queue"] for p in series)
    backlog_hours_to_clear = max_review_backlog / review_capacity_per_hour if review_capacity_per_hour else float("inf")
    reviewer_utilization = min(
        1.0,
        (images_per_hour_in * review_fraction) / review_capacity_per_hour if review_capacity_per_hour else 0,
    )
    annual_patients = num_sites * patients_per_site_per_day * 250  # 250 working days/year

    bottleneck = max(
        [("upload_bandwidth", upload_capacity_per_hour),
         ("ai_processing", ai_capacity_per_hour),
         ("human_review", review_capacity_per_hour)],
        key=lambda kv: images_per_hour_in / kv[1] if kv[1] else float("inf"),
    )[0]

    return {
        "inputs": {
            "num_sites": num_sites, "patients_per_site_per_day": patients_per_site_per_day,
            "images_per_patient": images_per_patient, "image_size_mb": image_size_mb,
            "upload_bandwidth_mbps": upload_bandwidth_mbps, "ai_seconds_per_image": ai_seconds_per_image,
            "review_fraction": review_fraction, "review_seconds": review_seconds,
            "num_reviewers": num_reviewers, "sim_days": sim_days,
        },
        "capacity_per_hour": {
            "images_in": round(images_per_hour_in, 1),
            "upload": round(upload_capacity_per_hour, 1),
            "ai": round(ai_capacity_per_hour, 1),
            "review": round(review_capacity_per_hour, 1),
        },
        "summary": {
            "annual_patients_capacity": int(annual_patients),
            "max_review_backlog_images": round(max_review_backlog, 1),
            "backlog_clear_time_hours": round(backlog_hours_to_clear, 1),
            "reviewer_utilization_pct": round(reviewer_utilization * 100, 1),
            "bottleneck": bottleneck,
        },
        "series": series[::max(1, total_hours // 200)],  # downsample for the chart
    }
