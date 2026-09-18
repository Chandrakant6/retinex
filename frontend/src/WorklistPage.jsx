import { useEffect, useState } from 'react';
import { listCases, reportUrl } from './api';
import { LEVEL_COLORS } from './lib.jsx';

export default function WorklistPage() {
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
          <h1 className="page-title">Worklist</h1>
          <p className="page-subtitle">
            Referable and inconsistent cases are surfaced first. Reload after screening new images.
          </p>
        </div>
        <button className="btn" onClick={load}>Refresh</button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        {cases === null ? (
          <div className="empty-state">Loading…</div>
        ) : cases.length === 0 ? (
          <div className="empty-state">No cases yet — screen an image to get started.</div>
        ) : (
          <table className="worklist-table">
            <thead>
              <tr>
                <th>ID</th><th>Grade</th><th>Referable</th><th>Consistent</th><th>Status</th><th>Time</th><th></th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td>{c.id}</td>
                  <td>
                    {c.status === 'complete' ? (
                      <span className="level-pill" style={{ background: LEVEL_COLORS[c.grading.icdr_level] }}>
                        {c.grading.icdr_level} — {c.grading.icdr_label}
                      </span>
                    ) : (
                      <span className="status-pill rejected">rejected</span>
                    )}
                  </td>
                  <td>{c.status === 'complete' ? (c.grading.referable ? '🔴 yes' : '🟢 no') : '—'}</td>
                  <td>{c.status === 'complete' ? (c.evidence.consistent ? '✓' : '⚠') : '—'}</td>
                  <td>
                    {c.status === 'rejected' ? (
                      <span className="status-pill rejected">quality reject</span>
                    ) : c.review ? (
                      <span className="status-pill reviewed">reviewed</span>
                    ) : (
                      <span className="status-pill pending">pending review</span>
                    )}
                  </td>
                  <td>{new Date(c.created_at).toLocaleTimeString()}</td>
                  <td>
                    {c.status === 'complete' && (
                      <a className="link-btn" href={reportUrl(c.id)} target="_blank" rel="noreferrer">report</a>
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
