import { useEffect, useState } from 'react';
import { listCases, reportUrl } from './api';
import { LEVEL_COLORS } from './lib.jsx';
import { useI18n } from './i18n/I18nContext.jsx';

export default function WorklistPage() {
  const { t } = useI18n();
  const [cases, setCases] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    try {
      const data = await listCases();
      setCases(data.cases);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div>
          <h1 className="page-title">{t('worklistTitle')}</h1>
          <p className="page-subtitle">{t('worklistSubtitle')}</p>
        </div>
        <button className="btn" onClick={load}>{t('refresh')}</button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        {cases === null ? (
          <div className="empty-state">{t('worklistLoading')}</div>
        ) : cases.length === 0 ? (
          <div className="empty-state">{t('worklistEmpty')}</div>
        ) : (
          <table className="worklist-table">
            <thead>
              <tr>
                <th>{t('colId')}</th><th>{t('colGrade')}</th><th>{t('colReferable')}</th>
                <th>{t('colConsistent')}</th><th>{t('colStatus')}</th><th>{t('colTime')}</th><th></th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td>{c.id}</td>
                  <td>
                    {c.status === 'complete' ? (
                      <span className="level-pill" style={{ background: LEVEL_COLORS[c.grading.icdr_level] }}>
                        {c.grading.icdr_level} — {t(`level_${c.grading.icdr_level}`)}
                      </span>
                    ) : (
                      <span className="status-pill rejected">{t('statusRejected')}</span>
                    )}
                  </td>
                  <td>{c.status === 'complete' ? (c.grading.referable ? `🔴 ${t('yes')}` : `🟢 ${t('no')}`) : '—'}</td>
                  <td>{c.status === 'complete' ? (c.evidence.consistent ? '✓' : '⚠') : '—'}</td>
                  <td>
                    {c.status === 'rejected' ? (
                      <span className="status-pill rejected">{t('statusQualityReject')}</span>
                    ) : c.review ? (
                      <span className="status-pill reviewed">{t('statusReviewed')}</span>
                    ) : (
                      <span className="status-pill pending">{t('statusPending')}</span>
                    )}
                  </td>
                  <td>{new Date(c.created_at).toLocaleTimeString()}</td>
                  <td>
                    {c.status === 'complete' && (
                      <a className="link-btn" href={reportUrl(c.id)} target="_blank" rel="noreferrer">{t('reportLink')}</a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
