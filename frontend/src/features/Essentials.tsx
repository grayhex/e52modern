import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useApi, usePreferences } from '../state/app';
import { useModels } from '../api/queries';
import { ErrorMessage } from '../components/ui';
import { SectionPanel, StatusIndicator } from '../components/kit';
import { essentialsListSchema, essentialsSchema, simpleSchema } from '../api/revive';

/** Verified Essentials: per-model profiles over existing catalog cards; static compatibility, never hardware claims. */
export default function Essentials() {
  const api = useApi();
  const { t } = usePreferences();
  const models = useModels();
  const [profile, setProfile] = useState('offline');
  const [model, setModel] = useState('nokia-e52');
  const list = useQuery({
    queryKey: ['essentials'],
    queryFn: () => api.request('/api/catalog', { action: 'essentials' }, essentialsListSchema),
  });
  const result = useQuery({
    queryKey: ['essentials', profile, model],
    queryFn: () =>
      api.request('/api/catalog', { action: 'essentials', profile, model }, essentialsSchema),
    retry: false,
  });
  const save = useMutation({
    mutationFn: () =>
      api.request(
        '/api/catalog',
        { action: 'essentials-collection', profile, model },
        simpleSchema,
      ),
  });
  const selectable = models.filter((m) => m.id !== 'nokia-n95-family' && m.id !== 'nokia-n97-mini');
  return (
    <SectionPanel title={t('Verified Essentials', 'Проверенные наборы')} id="essentials">
      <p className="k-note-line">{list.data?.note}</p>
      <div className="rv-form">
        <label>
          {t('Phone model', 'Модель телефона')}
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {selectable.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="rv-profiles" role="group" aria-label={t('Profile', 'Профиль')}>
        {list.data?.profiles.map((p) => (
          <button
            key={p.id}
            type="button"
            className="rv-profile"
            aria-pressed={profile === p.id}
            data-essentials={p.id}
            onClick={() => setProfile(p.id)}
          >
            <strong>{t(p.title.en, p.title.ru)}</strong>
          </button>
        ))}
      </div>
      {result.error && <ErrorMessage error={result.error} />}
      {result.data && !result.data.applicable && (
        <p role="status" data-testid="essentials-na">
          {result.data.reason}
        </p>
      )}
      {result.data?.applicable && (
        <>
          <ul className="k-list" data-testid="essentials-items">
            {result.data.items.map((i) => (
              <li key={i.id} data-item={i.id} data-eligible={i.eligible}>
                <span className="rv-check-text">
                  <strong>
                    {i.name} {i.version}
                  </strong>
                  <small>
                    {i.eligible
                      ? `${t('licence', 'лицензия')}: ${i.licence ?? '?'} · ${t('network', 'сеть')}: ${i.network ?? '?'} · ${t('hardware', 'железо')}: ${i.evidence?.hardware} · ${t('installation', 'установка')}: ${i.evidence?.installation}`
                      : i.reasons.join(' · ')}
                  </small>
                </span>
                <StatusIndicator tone={i.eligible ? 'info' : 'off'}>
                  {i.eligible
                    ? t('static-compatible', 'статически совместимо')
                    : t('not offered', 'не предлагается')}
                </StatusIndicator>
              </li>
            ))}
          </ul>
          <p className="k-note-line" data-testid="essentials-order">
            {t('Install order', 'Порядок установки')}: {result.data.order.join(' → ') || '—'} ·{' '}
            {Math.round(result.data.bytes / 1024)} KiB
          </p>
          <p className="k-note-line">{result.data.statement}</p>
          <button
            type="button"
            className="k-btn k-btn--primary"
            disabled={result.data.eligible_ids.length === 0 || save.isPending}
            onClick={() => save.mutate()}
          >
            {t('Save as a collection', 'Сохранить как набор')}
          </button>
          {save.isSuccess && (
            <p role="status" data-testid="essentials-saved">
              {t(
                'Saved: it now appears in the collections above; transfer copies files, you install on the phone.',
                'Сохранено: набор появился выше в списке; передача копирует файлы, установка — на телефоне.',
              )}
            </p>
          )}
          {save.error && <ErrorMessage error={save.error} />}
        </>
      )}
      <h3>{t('How to use it in 2026', 'Как пользоваться в 2026 году')}</h3>
      <ul>
        {(list.data?.guide.en ?? []).map((line, i) => (
          <li key={i}>{t(line, list.data?.guide.ru[i] ?? line)}</li>
        ))}
      </ul>
    </SectionPanel>
  );
}
