import { createContext, useContext, useEffect, useState, type PropsWithChildren } from 'react';
import { ApiClient } from '../api/client';
const ApiContext = createContext<ApiClient | null>(null);
export function ApiProvider({ client, children }: PropsWithChildren<{ client: ApiClient }>) {
  return <ApiContext value={client}>{children}</ApiContext>;
}
// eslint-disable-next-line react-refresh/only-export-components
export function useApi() {
  const client = useContext(ApiContext);
  if (!client) throw Error('API provider missing');
  return client;
}
type Preferences = {
  language: 'ru' | 'en';
  theme: 'system' | 'light' | 'dark';
  device: string;
  setDevice: (id: string) => void;
  setLanguage: (value: 'ru' | 'en') => void;
  setTheme: (value: 'system' | 'light' | 'dark') => void;
  t: (en: string, ru: string) => string;
};
const PreferencesContext = createContext<Preferences | null>(null);
function saved(key: string) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function persist(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* Private browsing may deny storage. */
  }
}
export function PreferencesProvider({ children }: PropsWithChildren) {
  const [language, setLanguageState] = useState<'ru' | 'en'>(
    saved('symport-language') === 'en' ? 'en' : 'ru',
  );
  const [theme, setThemeState] = useState<Preferences['theme']>(() => {
    const value = saved('symport-theme');
    return value === 'dark' || value === 'light' ? value : 'system';
  });
  const [device, setDevice] = useState('');
  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)');
    const apply = () => {
      document.documentElement.dataset.theme =
        theme === 'system' ? (media.matches ? 'dark' : 'light') : theme;
    };
    apply();
    media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, [theme]);
  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);
  return (
    <PreferencesContext
      value={{
        language,
        theme,
        device,
        setDevice,
        setLanguage: (value) => {
          setLanguageState(value);
          persist('symport-language', value);
        },
        setTheme: (value) => {
          setThemeState(value);
          persist('symport-theme', value);
        },
        t: (en, ru) => (language === 'en' ? en : ru),
      }}
    >
      {children}
    </PreferencesContext>
  );
}
// eslint-disable-next-line react-refresh/only-export-components
export function usePreferences() {
  const value = useContext(PreferencesContext);
  if (!value) throw Error('Preferences provider missing');
  return value;
}
