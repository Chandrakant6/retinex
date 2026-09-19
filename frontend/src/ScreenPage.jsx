import { useEffect, useRef, useState } from 'react';
import { screenImage, submitReview, reportUrl } from './api';
import { LEVEL_COLORS } from './lib.jsx';
import { useI18n } from './i18n/I18nContext.jsx';

function ProbBars({ probabilities, t }) {
  return (
    <div className="prob-bars">
      {probabilities.map((p, i) => (
        <div className="prob-row" key={i}>
          <span className="prob-label">{i}: {t(`level_${i}`)}</span>
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
  // Tab labels intentionally stay untranslated: "Grad-CAM" is a proper
  // technical term with no standard translation, and "Enhanced/Original/
  // Lesions" read fine as short image-viewer labels even in a non-English
  // UI, similar to how a camera app's mode names are often left in
  // English. Translate these too if that turns out not to hold for a
  // given language — nothing else depends on this choice.
  const [active, setActive] = useState('gradcam');
  const [opacity, setOpacity] = useState(0.7);
  const overlayTabs = new Set(['gradcam', 'lesions']);
  const { t } = useI18n();

  return (
    <div className="image-tabs">
      <div className="tab-bar">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`tab-btn ${active === tab.key ? 'active' : ''}`}
            onClick={() => setActive(tab.key)}
          >
            {tab.label}
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

function EvidencePanel({ evidence, t }) {
  return (
    <div className="evidence-panel">
      <div className="chips">
        <span className="chip">{evidence.microaneurysm_count} {t('microaneurysms')}</span>
        <span className="chip">{evidence.hemorrhage_count} {t('hemorrhages')}</span>
        <span className="chip">{evidence.exudate_area_pct}% {t('exudateArea')}</span>
        {evidence.cam_lesion_overlap_pct != null && (
          <span className="chip">{evidence.cam_lesion_overlap_pct}{t('lesionsInAttention')}</span>
        )}
      </div>
      {evidence.consistent ? (
        <p className="consistency-flag ok">{t('consistentOk')}</p>
      ) : (
        <p className="consistency-flag warn">{t('consistentWarn')}</p>
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
  const { t } = useI18n();
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
      <h1 className="page-title">{t('screenTitle')}</h1>
      <p className="page-subtitle">
        {t('screenSubtitle')}
        {engineInfo?.engine === 'mock' && (
          <> &nbsp;<span className="chip">{t('demoModeChip')}</span></>
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
          <p>{t('dropzoneText')}</p>
          <p className="hint">{t('dropzoneHint')}</p>
          <input
            ref={fileInputRef} type="file" accept="image/*" capture="environment" hidden
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </div>
      )}

      {status === 'loading' && (
        <div className="card loading">
          <div className="spinner" />
          <p>{t('loadingText')}</p>
        </div>
      )}

      {status === 'rejected' && result && (
        <div className="card rejected-card">
          <h2>{t('rejectedTitle')}</h2>
          <p>{t('qualityScoreLabel')}: {(result.quality.score * 100).toFixed(0)}%</p>
          <ul>
            {result.quality.reasons.map((r) => <li key={r}>{t(`reason_${r}`)}</li>)}
          </ul>
          <p className="guidance">
            {t('guidancePrefix')} {result.quality.reasons.map((r) => t(`reason_${r}`)).join(', ')}.
          </p>
          <button className="btn primary" onClick={reset}>{t('tryAnotherImage')}</button>
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
                {t('levelLabel')} {result.grading.icdr_level} — {t(`level_${result.grading.icdr_level}`)}
              </div>
              <p className="referable-line">
                {result.grading.referable ? t('referableYes') : t('referableNo')}
                {' · '}{t('confidenceLabel')}: {(result.grading.confidence * 100).toFixed(0)}%
              </p>
              <div className="recommendation">{t(`rec_${result.grading.recommendation_code}`)}</div>

              <ProbBars probabilities={result.grading.probabilities} t={t} />
              <EvidencePanel evidence={result.evidence} t={t} />

              <div className="meta-row">
                <span>{t('metaQuality')}: {(result.quality.score * 100).toFixed(0)}% ({result.quality.tier})</span>
                <span>{t('metaProcessedIn')} {result.processing_time_sec}s</span>
                <span>{t('metaEngine')}: {result.engine}</span>
              </div>

              {!reviewed ? (
                <>
                  <div className="review-timer">⏱ {elapsed.toFixed(1)}s {t('reviewingTimer')}</div>
                  <div className="review-actions">
                    <button className="btn primary" onClick={() => handleDecision('accept')}>{t('accept')}</button>
                    {[0, 1, 2, 3, 4].map((lvl) => (
                      <button key={lvl} className="level-btn" title={`${t('overrideTitle')} ${lvl}`}
                        onClick={() => handleDecision('override', lvl)}>{lvl}</button>
                    ))}
                  </div>
                  <p className="keyhint">{t('keyhint')}</p>
                </>
              ) : (
                <div className="reviewed-note">{t('reviewedNote')} ({elapsed.toFixed(1)}s)</div>
              )}

              {sessionStats && (
                <div className="session-stats">
                  <b>{t('sessionLabel')}:</b> {sessionStats.reviewed} {t('sessionReviewed')} ·
                  {' '}{t('sessionAvg')} {sessionStats.avg_review_time_sec}s ·
                  {' '}{sessionStats.under_30s_pct}% {t('sessionUnder30')} ·
                  {' '}{sessionStats.override_rate_pct}% {t('sessionOverridden')}
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                <a className="btn ghost" href={reportUrl(result.id)} target="_blank" rel="noreferrer">
                  {t('openReport')}
                </a>
                <button className="btn ghost" onClick={reset}>{t('screenAnother')}</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
