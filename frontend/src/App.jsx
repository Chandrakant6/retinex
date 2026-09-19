import { useEffect, useState } from 'react';
import { health } from './api';
import { useI18n } from './i18n/I18nContext.jsx';
import ScreenPage from './ScreenPage.jsx';
import WorklistPage from './WorklistPage.jsx';
import PlanningPage from './PlanningPage.jsx';

export default function App() {
  const [tab, setTab] = useState('screen');
  const [engineInfo, setEngineInfo] = useState(null);
  const { t, lang, setLang, languages } = useI18n();

  const TABS = [
    { key: 'screen', label: t('navScreen') },
    { key: 'worklist', label: t('navWorklist') },
    { key: 'planning', label: t('navPlanning') },
  ];

  useEffect(() => {
    health().then(setEngineInfo).catch(() => setEngineInfo({ status: 'unreachable' }));
  }, []);

  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="brand">{t('brand')}<small>{t('brandSubtitle')}</small></div>
        <nav>
          {TABS.map((tItem) => (
            <button key={tItem.key} className={tab === tItem.key ? 'active' : ''} onClick={() => setTab(tItem.key)}>
              {tItem.label}
            </button>
          ))}
        </nav>
        <select
          className="lang-select"
          value={lang}
          onChange={(e) => setLang(e.target.value)}
          aria-label="Language"
        >
          {Object.entries(languages).map(([code, info]) => (
            <option key={code} value={code}>{info.native}</option>
          ))}
        </select>
        {engineInfo && (
          <span className={`engine-pill ${engineInfo.engine === 'mock' ? 'mock' : ''}`}>
            {engineInfo.status === 'unreachable' ? t('engineUnreachable')
              : engineInfo.engine === 'mock' ? t('engineMock') : t('engineTensorflow')}
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
