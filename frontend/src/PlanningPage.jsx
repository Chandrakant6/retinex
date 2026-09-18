import { useEffect, useState } from 'react';
import { runSimulation } from './api';
import { LineChart } from './lib.jsx';

const DEFAULTS = {
  num_sites: 20,
  patients_per_site_per_day: 20,
  images_per_patient: 2,
  image_size_mb: 2.5,
  upload_bandwidth_mbps: 5.0,
  ai_seconds_per_image: 2.0,
  review_fraction: 0.35,
  review_seconds: 25,
  num_reviewers: 3,
  sim_days: 30,
};

const CONTROLS = [
  { key: 'num_sites', label: 'Camera sites', min: 1, max: 100, step: 1 },
  { key: 'patients_per_site_per_day', label: 'Patients / site / day', min: 1, max: 100, step: 1 },
  { key: 'upload_bandwidth_mbps', label: 'Upload bandwidth (Mbps)', min: 0.5, max: 50, step: 0.5 },
  { key: 'ai_seconds_per_image', label: 'AI seconds / image', min: 0.2, max: 10, step: 0.1 },
  { key: 'review_fraction', label: 'Fraction needing review', min: 0.05, max: 1, step: 0.05 },
  { key: 'review_seconds', label: 'Review seconds / image', min: 5, max: 120, step: 1 },
  { key: 'num_reviewers', label: 'Ophthalmologists / reviewers', min: 1, max: 30, step: 1 },
];

export default function PlanningPage() {
  const [params, setParams] = useState(DEFAULTS);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function simulate(p) {
    try {
      const r = await runSimulation(p);
      setResult(r);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => { simulate(params); /* eslint-disable-next-line */ }, []);

  function update(key, value) {
    const next = { ...params, [key]: value };
    setParams(next);
    simulate(next);
  }

  return (
    <div>
      <h1 className="page-title">District screening capacity planning</h1>
      <p className="page-subtitle">
        Adjust the sliders to size a screening program — find the smallest reviewer/bandwidth
        setup that keeps the backlog under control. Ported from this Python model to Simulink
        is a direct block-for-block translation (see doc/simulation.md).
      </p>

      {error && <div className="error-banner">{error}</div>}

      <div className="planning-grid">
        <div className="card control-group">
          {CONTROLS.map((c) => (
            <div className="control-row" key={c.key}>
              <label>
                <span>{c.label}</span>
                <span className="value">{params[c.key]}</span>
              </label>
              <input
                type="range" min={c.min} max={c.max} step={c.step}
                value={params[c.key]}
                onChange={(e) => update(c.key, parseFloat(e.target.value))}
              />
            </div>
          ))}
        </div>

        <div>
          {result && (
            <>
              <div className="stat-grid">
                <div className="card stat-box">
                  <div className="stat-value">{result.summary.annual_patients_capacity.toLocaleString()}</div>
                  <div className="stat-label">Patients / year at these settings</div>
                </div>
                <div className={`card stat-box ${result.summary.backlog_clear_time_hours > 48 ? 'warn' : ''}`}>
                  <div className="stat-value">{result.summary.backlog_clear_time_hours}h</div>
                  <div className="stat-label">Time to clear peak review backlog</div>
                </div>
                <div className="card stat-box">
                  <div className="stat-value">{result.summary.reviewer_utilization_pct}%</div>
                  <div className="stat-label">Reviewer utilization</div>
                </div>
                <div className="card stat-box">
                  <div className="stat-value" style={{ fontSize: 16, textTransform: 'capitalize' }}>
                    {result.summary.bottleneck.replace('_', ' ')}
                  </div>
                  <div className="stat-label">Current bottleneck</div>
                </div>
              </div>

              <div className="bottleneck-note">
                Capacity per hour — upload: {result.capacity_per_hour.upload} · AI: {result.capacity_per_hour.ai} ·
                {' '}review: {result.capacity_per_hour.review} · incoming: {result.capacity_per_hour.images_in} images/hr
              </div>

              <div className="card chart-card">
                <h3>Queue length over the simulated period</h3>
                <LineChart
                  xLabel="hour"
                  yLabel="queue length (images)"
                  series={[
                    { name: 'Upload', color: '#8a9c1e', points: result.series.map((p) => ({ x: p.hour, y: p.upload_queue })) },
                    { name: 'AI', color: '#c99a1e', points: result.series.map((p) => ({ x: p.hour, y: p.ai_queue })) },
                    { name: 'Review', color: '#b13a3a', points: result.series.map((p) => ({ x: p.hour, y: p.review_queue })) },
                  ]}
                />
                <div className="legend">
                  <span><i style={{ background: '#8a9c1e' }} /> Upload queue</span>
                  <span><i style={{ background: '#c99a1e' }} /> AI processing queue</span>
                  <span><i style={{ background: '#b13a3a' }} /> Human review queue</span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
