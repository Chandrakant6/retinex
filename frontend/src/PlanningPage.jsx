import { useEffect, useState } from 'react';
import { runSimulation } from './api';
import { LineChart } from './lib.jsx';
import { useI18n } from './i18n/I18nContext.jsx';

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

// keys map to translation keys "ctrl_<key>" in translations.js
const CONTROLS = [
  { key: 'num_sites', min: 1, max: 100, step: 1 },
  { key: 'patients_per_site_per_day', min: 1, max: 100, step: 1 },
  { key: 'upload_bandwidth_mbps', min: 0.5, max: 50, step: 0.5 },
  { key: 'ai_seconds_per_image', min: 0.2, max: 10, step: 0.1 },
  { key: 'review_fraction', min: 0.05, max: 1, step: 0.05 },
  { key: 'review_seconds', min: 5, max: 120, step: 1 },
  { key: 'num_reviewers', min: 1, max: 30, step: 1 },
];

export default function PlanningPage() {
  const { t } = useI18n();
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
      <h1 className="page-title">{t('planningTitle')}</h1>
      <p className="page-subtitle">{t('planningSubtitle')}</p>

      {error && <div className="error-banner">{error}</div>}

      <div className="planning-grid">
        <div className="card control-group">
          {CONTROLS.map((c) => (
            <div className="control-row" key={c.key}>
              <label>
                <span>{t(`ctrl_${c.key}`)}</span>
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
                  <div className="stat-label">{t('statPatientsPerYear')}</div>
                </div>
                <div className={`card stat-box ${result.summary.backlog_clear_time_hours > 48 ? 'warn' : ''}`}>
                  <div className="stat-value">{result.summary.backlog_clear_time_hours}h</div>
                  <div className="stat-label">{t('statBacklogClear')}</div>
                </div>
                <div className="card stat-box">
                  <div className="stat-value">{result.summary.reviewer_utilization_pct}%</div>
                  <div className="stat-label">{t('statUtilization')}</div>
                </div>
                <div className="card stat-box">
                  <div className="stat-value" style={{ fontSize: 16, textTransform: 'capitalize' }}>
                    {t(`bottleneck_${result.summary.bottleneck}`)}
                  </div>
                  <div className="stat-label">{t('statBottleneck')}</div>
                </div>
              </div>

              <div className="bottleneck-note">
                {t('capacityNote')} {result.capacity_per_hour.upload} · {t('capacityAi')} {result.capacity_per_hour.ai} ·
                {' '}{t('capacityReview')} {result.capacity_per_hour.review} ·
                {' '}{t('capacityIncoming')} {result.capacity_per_hour.images_in} {t('capacityImagesPerHr')}
              </div>

              <div className="card chart-card">
                <h3>{t('chartTitle')}</h3>
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
                  <span><i style={{ background: '#8a9c1e' }} /> {t('legendUpload')}</span>
                  <span><i style={{ background: '#c99a1e' }} /> {t('legendAi')}</span>
                  <span><i style={{ background: '#b13a3a' }} /> {t('legendReview')}</span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
