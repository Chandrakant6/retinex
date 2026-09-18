import { useEffect, useRef, useState } from 'react';
import { screenImage, submitReview, reportUrl } from './api';
import { LEVEL_COLORS, LEVEL_LABELS } from './lib.jsx';

function ProbBars({ probabilities }) {
  return (
    <div className="prob-bars">
      {probabilities.map((p, i) => (
        <div className="prob-row" key={i}>
          <span className="prob-label">{i}: {LEVEL_LABELS[i]}</span>
          <div className="prob-track">
            <div className="prob-fill" style={{ width: `${p * 100}%`, background: LEVEL_COLORS[i] }} />
          </div>
          <span className="prob-val">{(p * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  );
}

function ImageViewer({ images }) {
  const tabs = [
    { key: 'enhanced', label: 'Enhanced' },
    { key: 'original', label: 'Original' },
    { key: 'gradcam', label: 'Grad-CAM' },
    { key: 'lesions', label: 'Lesions' },
  ];
  const [active, setActive] = useState('gradcam');
  const [opacity, setOpacity] = useState(0.7);
  const overlayTabs = new Set(['gradcam', 'lesions']);

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
      <div className="image-frame">
        <img src={images.enhanced} alt="enhanced fundus" />
        {overlayTabs.has(active) && (
          <img src={images[active]} alt={active} style={{ opacity }} />
        )}
        {!overlayTabs.has(active) && active === 'original' && (
          <img src={images.original} alt="original" />
        )}
      </div>
      {overlayTabs.has(active) && (
        <div className="overlay-controls">
          <span>Overlay opacity</span>
          <input
            type="range" min="0" max="1" step="0.05" value={opacity}
            onChange={(e) => setOpacity(parseFloat(e.target.value))}
          />
        </div>
      )}
    </div>
  );
}

function EvidencePanel({ evidence }) {
  return (
    <div className="evidence-panel">
      <div className="chips">
        <span className="chip">{evidence.microaneurysm_count} microaneurysms</span>
        <span className="chip">{evidence.hemorrhage_count} hemorrhages</span>
        <span className="chip">{evidence.exudate_area_pct}% exudate area</span>
        {evidence.cam_lesion_overlap_pct != null && (
          <span className="chip">{evidence.cam_lesion_overlap_pct}% lesions inside attention region</span>
        )}
      </div>
      {evidence.consistent ? (
        <p className="consistency-flag ok">✓ AI grade is consistent with visible lesion evidence.</p>
      ) : (
        <p className="consistency-flag warn">⚠ Evidence and AI grade disagree — review carefully.</p>
      )}
      {evidence.notes?.length > 0 && (
        <ul className="evidence-notes">
          {evidence.notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      )}
    </div>
  );
}

export default function ScreenPage({ engineInfo }) {
  const [status, setStatus] = useState('idle'); // idle | loading | rejected | complete
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [reviewed, setReviewed] = useState(false);
  const [sessionStats, setSessionStats] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const resultStartRef = useRef(null);
  const fileInputRef = useRef(null);
  const timerRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  async function handleFile(file) {
    if (!file) return;
    setStatus('loading');
    setError(null);
    setResult(null);
    setReviewed(false);
    try {
      const data = await screenImage(file);
      setResult(data);
      setStatus(data.status);
      if (data.status === 'complete') {
        resultStartRef.current = performance.now();
        setElapsed(0);
      }
    } catch (e) {
      setError(e.message);
      setStatus('idle');
    }
  }

  useEffect(() => {
    if (status === 'complete' && !reviewed) {
      timerRef.current = setInterval(() => {
        setElapsed(((performance.now() - resultStartRef.current) / 1000));
      }, 200);
      return () => clearInterval(timerRef.current);
    }
  }, [status, reviewed]);

  async function handleDecision(decision, overrideLevel = null) {
    if (!result || reviewed) return;
    clearInterval(timerRef.current);
    const reviewTimeSec = parseFloat(((performance.now() - resultStartRef.current) / 1000).toFixed(1));
    try {
      const res = await submitReview({ id: result.id, decision, overrideLevel, reviewTimeSec });
      setSessionStats(res.session_stats);
      setReviewed(true);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    function onKey(e) {
      if (status !== 'complete' || reviewed) return;
      if (e.key === 'a' || e.key === 'Enter') handleDecision('accept');
      if (['0', '1', '2', '3', '4'].includes(e.key)) handleDecision('override', Number(e.key));
      if (e.key === 'n' || e.key === 'Escape') reset();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, reviewed, result]);

  function reset() {
    setStatus('idle');
    setResult(null);
    setError(null);
    setReviewed(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  return (
    <div>
      <h1 className="page-title">Screen a fundus image</h1>
      <p className="page-subtitle">
        Upload or capture a retinal photograph. Images that aren&rsquo;t gradable are flagged for
        recapture before anything is graded.
        {engineInfo?.engine === 'mock' && (
          <> &nbsp;<span className="chip">Demo mode — no trained model loaded</span></>
        )}
      </p>

      {error && <div className="error-banner">{error}</div>}

      {status === 'idle' && (
        <div
          className={`dropzone ${dragOver ? 'drag' : ''}`}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files?.[0]); }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="icon">📷</div>
          <p>Drop a fundus image here, or click to browse</p>
          <p className="hint">JPG or PNG · works from a phone camera in the field</p>
          <input
            ref={fileInputRef} type="file" accept="image/*" capture="environment" hidden
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </div>
      )}

      {status === 'loading' && (
        <div className="card loading">
          <div className="spinner" />
          <p>Assessing quality, enhancing, grading…</p>
        </div>
      )}

      {status === 'rejected' && result && (
        <div className="card rejected-card">
          <h2>⚠ Image rejected</h2>
          <p>Quality score: {(result.quality.score * 100).toFixed(0)}%</p>
          <ul>
            {result.quality.reasons.map((r) => <li key={r}>{r.replace(/_/g, ' ')}</li>)}
          </ul>
          <p className="guidance">{result.quality.guidance}</p>
          <button className="btn primary" onClick={reset}>Try another image</button>
        </div>
      )}

      {status === 'complete' && result && (
        <div className="card">
          <div className="result-grid">
            <div>
              <ImageViewer images={result.images} />
            </div>
            <div>
              <div className="grade-badge" style={{ background: LEVEL_COLORS[result.grading.icdr_level] }}>
                Level {result.grading.icdr_level} — {result.grading.icdr_label}
              </div>
              <p className="referable-line">
                {result.grading.referable ? '🔴 Referable DR' : '🟢 Not referable'}
                {' · '}Confidence: {(result.grading.confidence * 100).toFixed(0)}%
              </p>
              <div className="recommendation">{result.grading.recommendation}</div>

              <ProbBars probabilities={result.grading.probabilities} />
              <EvidencePanel evidence={result.evidence} />

              <div className="meta-row">
                <span>Quality: {(result.quality.score * 100).toFixed(0)}% ({result.quality.tier})</span>
                <span>Processed in {result.processing_time_sec}s</span>
                <span>Engine: {result.engine}</span>
              </div>

              {!reviewed ? (
                <>
                  <div className="review-timer">⏱ {elapsed.toFixed(1)}s reviewing</div>
                  <div className="review-actions">
                    <button className="btn primary" onClick={() => handleDecision('accept')}>✓ Accept (A)</button>
                    {[0, 1, 2, 3, 4].map((lvl) => (
                      <button key={lvl} className="level-btn" title={`Override to level ${lvl}`}
                        onClick={() => handleDecision('override', lvl)}>{lvl}</button>
                    ))}
                  </div>
                  <p className="keyhint">
                    <kbd>A</kbd> accept · <kbd>0</kbd>–<kbd>4</kbd> override level · <kbd>N</kbd> next image
                  </p>
                </>
              ) : (
                <div className="reviewed-note">Review recorded ✓ ({elapsed.toFixed(1)}s)</div>
              )}

              {sessionStats && (
                <div className="session-stats">
                  <b>Session:</b> {sessionStats.reviewed} reviewed · avg {sessionStats.avg_review_time_sec}s ·
                  {' '}{sessionStats.under_30s_pct}% under 30s · {sessionStats.override_rate_pct}% overridden
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                <a className="btn ghost" href={reportUrl(result.id)} target="_blank" rel="noreferrer">
                  Open report ↗
                </a>
                <button className="btn ghost" onClick={reset}>Screen another image (N)</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
