import { useRef, useState } from 'react';
import { screenImage, submitReview } from './api';

const LEVEL_COLORS = ['#2e7d32', '#9e9d24', '#f9a825', '#ef6c00', '#c62828'];

function ProbBars({ probabilities }) {
  const labels = ['0: No DR', '1: Mild', '2: Moderate', '3: Severe', '4: PDR'];
  return (
    <div className="prob-bars">
      {probabilities.map((p, i) => (
        <div className="prob-row" key={i}>
          <span className="prob-label">{labels[i]}</span>
          <div className="prob-track">
            <div
              className="prob-fill"
              style={{ width: `${p * 100}%`, background: LEVEL_COLORS[i] }}
            />
          </div>
          <span className="prob-val">{(p * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  );
}

function ImageTabs({ images }) {
  const tabs = [
    { key: 'original', label: 'Original' },
    { key: 'enhanced', label: 'Enhanced' },
    ...(images.gradcam ? [{ key: 'gradcam', label: 'Grad-CAM' }] : []),
  ];
  const [active, setActive] = useState('enhanced');

  return (
    <div className="image-tabs">
      <div className="tab-bar">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`tab-btn ${active === t.key ? 'active' : ''}`}
            onClick={() => setActive(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <img className="preview-img" src={images[active]} alt={active} />
    </div>
  );
}

export default function App() {
  const [status, setStatus] = useState('idle'); // idle | loading | rejected | complete
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [reviewed, setReviewed] = useState(false);
  const [sessionStats, setSessionStats] = useState(null);
  const resultStartRef = useRef(null);
  const fileInputRef = useRef(null);

  async function handleFile(file) {
    if (!file) return;
    setStatus('loading');
    setError(null);
    setResult(null);
    setReviewed(false);
    try {
      const data = await screenImage(file);
      setResult(data);
      setStatus(data.status); // 'rejected' | 'complete'
      resultStartRef.current = performance.now();
    } catch (e) {
      setError(e.message);
      setStatus('idle');
    }
  }

  function onDrop(e) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  }

  async function handleDecision(decision) {
    if (!result || reviewed) return;
    const elapsedSec = ((performance.now() - resultStartRef.current) / 1000).toFixed(1);
    try {
      const res = await submitReview({
        id: result.id,
        decision,
        overrideLevel: decision === 'override' ? promptOverrideLevel() : null,
        reviewTimeSec: parseFloat(elapsedSec),
      });
      setSessionStats(res.session_stats);
      setReviewed(true);
    } catch (e) {
      setError(e.message);
    }
  }

  function promptOverrideLevel() {
    const v = window.prompt('Override ICDR level (0-4):', '2');
    const n = parseInt(v, 10);
    return Number.isFinite(n) ? Math.max(0, Math.min(4, n)) : null;
  }

  function reset() {
    setStatus('idle');
    setResult(null);
    setError(null);
    setReviewed(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  return (
    <div className="app">
      <header className="header">
        <h1>DR Screening — Prototype</h1>
        <p className="subtitle">Upload a fundus image for automated diabetic retinopathy screening</p>
      </header>

      {status === 'idle' && (
        <div
          className="dropzone"
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
        >
          <p>Drop a fundus image here, or click to browse</p>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </div>
      )}

      {status === 'loading' && (
        <div className="loading">
          <div className="spinner" />
          <p>Assessing quality, enhancing, grading…</p>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

      {status === 'rejected' && result && (
        <div className="rejected-card">
          <h2>⚠ Image Rejected</h2>
          <p className="quality-score">Quality score: {(result.quality.score * 100).toFixed(0)}%</p>
          <ul>
            {result.quality.reasons.map((r) => (
              <li key={r}>{r.replace(/_/g, ' ')}</li>
            ))}
          </ul>
          <p className="guidance">{result.quality.guidance}</p>
          <button className="btn" onClick={reset}>Try another image</button>
        </div>
      )}

      {status === 'complete' && result && (
        <div className="result-card">
          <div className="result-grid">
            <div className="result-left">
              <ImageTabs images={result.images} />
            </div>
            <div className="result-right">
              <div
                className="grade-badge"
                style={{ background: LEVEL_COLORS[result.grading.icdr_level] }}
              >
                Level {result.grading.icdr_level} — {result.grading.icdr_label}
              </div>
              <p className="referable">
                {result.grading.referable ? '🔴 Referable DR' : '🟢 Not referable'}
                {' '}· Confidence: {(result.grading.confidence * 100).toFixed(0)}%
              </p>

              <ProbBars probabilities={result.grading.probabilities} />

              <div className="meta-row">
                <span>Quality: {(result.quality.score * 100).toFixed(0)}%</span>
                <span>Processed in {result.processing_time_sec}s</span>
                <span>Engine: {result.engine.quality}/{result.engine.enhance}</span>
              </div>

              {!reviewed ? (
                <div className="review-actions">
                  <button className="btn accept" onClick={() => handleDecision('accept')}>
                    ✓ Accept
                  </button>
                  <button className="btn override" onClick={() => handleDecision('override')}>
                    ✎ Override
                  </button>
                </div>
              ) : (
                <div className="reviewed-note">Review recorded ✓</div>
              )}

              {sessionStats && (
                <div className="session-stats">
                  <strong>Session:</strong> {sessionStats.reviewed} reviewed ·{' '}
                  avg {sessionStats.avg_review_time_sec}s ·{' '}
                  {sessionStats.override_rate_pct}% override rate
                </div>
              )}

              <button className="btn ghost" onClick={reset}>Screen another image</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
