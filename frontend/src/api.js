const BASE = ''; // same-origin via vite proxy in dev, or same host in prod

export async function screenImage(file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/api/screen`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`screen failed: ${res.status}`);
  return res.json();
}

export async function submitReview({ id, decision, overrideLevel, reviewTimeSec }) {
  const res = await fetch(`${BASE}/api/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id,
      decision,
      override_level: overrideLevel ?? null,
      review_time_sec: reviewTimeSec,
    }),
  });
  if (!res.ok) throw new Error(`review failed: ${res.status}`);
  return res.json();
}
