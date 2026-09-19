import { createContext, useContext, useState, useCallback } from 'react';
import { TRANSLATIONS, LANGUAGES } from './translations.js';

const STORAGE_KEY = 'retinex_lang';
const FALLBACK_LANG = 'en';

const I18nCtx = createContext(null);

function detectInitialLang() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && TRANSLATIONS[saved]) return saved;
  } catch {
    // localStorage unavailable (e.g. private browsing) — fall through
  }
  return FALLBACK_LANG;
}

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(detectInitialLang);

  const setLang = useCallback((code) => {
    if (!TRANSLATIONS[code]) return;
    setLangState(code);
    try {
      localStorage.setItem(STORAGE_KEY, code);
    } catch {
      // ignore — language just won't persist across reloads
    }
  }, []);

  // t(key): looks up `key` in the current language, falling back to
  // English if missing (e.g. a new language file that hasn't translated
  // every key yet), and finally to the key itself so missing translations
  // are visible/debuggable rather than silently blank.
  const t = useCallback(
    (key) => TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS[FALLBACK_LANG]?.[key] ?? key,
    [lang]
  );

  return (
    <I18nCtx.Provider value={{ lang, setLang, t, languages: LANGUAGES }}>
      {children}
    </I18nCtx.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nCtx);
  if (!ctx) throw new Error('useI18n() must be used inside <I18nProvider>');
  return ctx;
}
