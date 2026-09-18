import { useEffect, useState } from 'react';
import { health } from './api';
import ScreenPage from './ScreenPage.jsx';
import WorklistPage from './WorklistPage.jsx';
import PlanningPage from './PlanningPage.jsx';

const TABS = [
  { key: 'screen', label: 'Screen' },
  { key: 'worklist', label: 'Worklist' },
  { key: 'planning', label: 'District Planning' },
];

export default function App() {
  const [tab, setTab] = useState('screen');
  const [engineInfo, setEngineInfo] = useState(null);

  useEffect(() => {
    health().then(setEngineInfo).catch(() => setEngineInfo({ status: 'unreachable' }));
  }, []);

  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="brand">Retinex<small>DR screening prototype</small></div>
        <nav>
          {TABS.map((t) => (
            <button key={t.key} className={tab === t.key ? 'active' : ''} onClick={() => setTab(t.key)}>
              {t.label}
            </button>
          ))}
        </nav>
        {engineInfo && (
          <span className={`engine-pill ${engineInfo.engine === 'mock' ? 'mock' : ''}`}>
            {engineInfo.status === 'unreachable' ? 'backend unreachable' : `engine: ${engineInfo.engine}`}
          </span>
        )}
      </div>
      <div className="main">
        {tab === 'screen' && <ScreenPage engineInfo={engineInfo} />}
        {tab === 'worklist' && <WorklistPage />}
        {tab === 'planning' && <PlanningPage />}
      </div>
    </div>
  );
}
