const BASE = ''; // same-origin via Vite proxy in dev, or same host in production

async function handle(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}${text ? ': ' + text : ''}`);
  }
  return res.json();
}

export function health() {
  return fetch(`${BASE}/api/health`).then(handle);
}

export function screenImage(file) {
  const form = new FormData();
  form.append('file', file);
  return fetch(`${BASE}/api/screen`, { method: 'POST', body: form }).then(handle);
}

export function submitReview({ id, decision, overrideLevel, reviewTimeSec }) {
  return fetch(`${BASE}/api/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id,
      decision,
      override_level: overrideLevel ?? null,
      review_time_sec: reviewTimeSec,
    }),
  }).then(handle);
}

export function listCases() {
  return fetch(`${BASE}/api/cases`).then(handle);
}

export function getMetrics() {
  return fetch(`${BASE}/api/metrics`).then(handle);
}

export function runSimulation(params) {
  return fetch(`${BASE}/api/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  }).then(handle);
}

export function reportUrl(id) {
  return `${BASE}/api/report/${id}`;
}
