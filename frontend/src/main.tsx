import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ApiClient } from './api/client';
import { ApiProvider, PreferencesProvider } from './state/app';
import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import '../../symport/web_assets/app.css';
import '../../symport/web_assets/compact.css';
import '../../symport/web_assets/nimbus.css';
import '../../symport/web_assets/preferences.css';
import '../../symport/web_assets/device-workspace.css';
import '../../symport/web_assets/lab.css';
import '../../symport/web_assets/ringtone.css';
import './style.css';
async function bootstrap() {
  let token = document.querySelector<HTMLMetaElement>('meta[name="symport-token"]')?.content;
  if (!token || token === '__SESSION_TOKEN__') {
    const response = await fetch(import.meta.env.DEV ? '/session.html' : '/');
    const html = await response.text();
    token = new DOMParser()
      .parseFromString(html, 'text/html')
      .querySelector<HTMLMetaElement>('meta[name="symport-token"]')?.content;
  }
  if (!token || token === '__SESSION_TOKEN__')
    throw Error('Open SymPort through its authenticated Python server.');
  const session = token;
  const client = new ApiClient(() => session);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 300000 }, mutations: { retry: false } },
  });
  const root = document.getElementById('root');
  if (!root) throw Error('Root missing');
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <ApiProvider client={client}>
          <PreferencesProvider>
            <ErrorBoundary>
              <App />
            </ErrorBoundary>
          </PreferencesProvider>
        </ApiProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
}
void bootstrap().catch(() => {
  const root = document.getElementById('root');
  if (root)
    createRoot(root).render(
      <main className="card">
        <h1>SymPort</h1>
        <p>
          Откройте SymPort через настроенный Python-сервер. / Open SymPort through its authenticated
          Python server.
        </p>
        <button onClick={() => location.reload()}>Обновить / Reload</button>
      </main>,
    );
});
