import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ZodType } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { ErrorMessage } from '../components/ui';
import { Download } from '../components/workspace';
import { SectionPanel, StatusIndicator, type Tone } from '../components/kit';
import {
  restorePreviewSchema,
  restoreResultSchema,
  settingsDownloadSchema,
  settingsStateSchema,
  simpleSchema,
} from '../api/revive';
import { st } from './statements';

const LEVEL: Record<string, [string, string, Tone]> = {
  exportable: ['Can be exported (read verified)', 'Можно экспортировать (чтение проверено)', 'ok'],
  unverified: ['Read not verified yet', 'Чтение ещё не проверено', 'unknown'],
  unavailable: ['Unavailable', 'Недоступно', 'off'],
  'manual-only': ['Manual only', 'Только вручную', 'warn'],
};
const NAME: Record<string, [string, string]> = {
  contacts: ['Contacts', 'Контакты'],
  calendar: ['Calendar', 'Календарь'],
  tasks: ['Tasks', 'Задачи'],
  sms: ['Messages (private)', 'Сообщения (приватные)'],
  notes: ['Notes', 'Заметки'],
  profiles: ['Profile settings', 'Настройки профилей'],
  'app-settings': ['Application settings', 'Настройки приложений'],
  'system-databases': ['System databases', 'Системные базы'],
};

/** "Settings and databases": capability-aware export with a versioned manifest, preview restore with read-back. */
export default function SettingsBackup({ device }: { device: string }) {
  const api = useApi();
  const cache = useQueryClient();
  const { t, language } = usePreferences();
  const [picked, setPicked] = useState<string[]>([]);
  const [consent, setConsent] = useState(false);
  const [preview, setPreview] = useState<ReturnType<typeof restorePreviewSchema.parse> | null>(
    null,
  );
  const [ackOther, setAckOther] = useState(false);
  const [sure, setSure] = useState(false);
  const call = <T,>(body: Record<string, unknown>, schema: ZodType<T>) =>
    api.request('/api/revive', body as never, schema);
  const state = useQuery({
    queryKey: ['revive', device, 'settings'],
    queryFn: () => call({ action: 'settings-state', device }, settingsStateSchema),
    staleTime: 0,
    retry: false,
  });
  const refresh = () => cache.invalidateQueries({ queryKey: ['revive', device, 'settings'] });
  const exp = useMutation({
    mutationFn: () =>
      call(
        {
          action: 'settings-export',
          device,
          categories: picked,
          confirm: true,
          owner_consent: consent,
        },
        simpleSchema,
      ),
    onSuccess: () => {
      setConsent(false);
      void refresh();
    },
  });
  const dl = useMutation({
    mutationFn: (backup: string) =>
      call({ action: 'settings-download', backup }, settingsDownloadSchema),
  });
  const prev = useMutation({
    mutationFn: ({ backup, category }: { backup: string; category: string }) =>
      call({ action: 'settings-restore-preview', device, backup, category }, restorePreviewSchema),
    onSuccess: setPreview,
  });
  const apply = useMutation({
    mutationFn: (p: NonNullable<typeof preview>) =>
      call(
        {
          action: 'settings-restore-apply',
          device,
          backup: p.backup,
          category: p.category,
          snapshot: p.snapshot,
          plan: p.plan,
          confirm: true,
          acknowledge_other_phone: ackOther,
        },
        restoreResultSchema,
      ),
    onSuccess: () => {
      setSure(false);
      void refresh();
    },
  });
  if (state.error) return <ErrorMessage error={state.error} />;
  if (!state.data) return null;
  const s = state.data;
  return (
    <SectionPanel title={t('Settings and databases', 'Настройки и базы')} id="settings-backup">
      <p className="k-note-line" data-testid="settings-statement">
        {st(language, s.statement)}
      </p>
      <ul className="k-list" data-testid="settings-categories">
        {s.categories.map((c) => (
          <li key={c.id} data-category={c.id} data-level={c.level}>
            <label className="rv-check-text">
              {c.level === 'exportable' ? (
                <span className="rv-check">
                  <input
                    type="checkbox"
                    checked={picked.includes(c.id)}
                    onChange={(e) =>
                      setPicked(
                        e.target.checked ? [...picked, c.id] : picked.filter((x) => x !== c.id),
                      )
                    }
                  />
                  <strong>{t(...(NAME[c.id] ?? [c.id, c.id]))}</strong>
                </span>
              ) : (
                <strong>{t(...(NAME[c.id] ?? [c.id, c.id]))}</strong>
              )}
              <small>
                {t(c.reason.en, c.reason.ru)}
                {c.sensitive
                  ? ` · ${t('stored separately, never in reports', 'хранится отдельно, не попадает в отчёты')}`
                  : ''}
              </small>
            </label>
            <StatusIndicator tone={LEVEL[c.level]?.[2] ?? 'unknown'}>
              {t(LEVEL[c.level]?.[0] ?? c.level, LEVEL[c.level]?.[1] ?? c.level)}
            </StatusIndicator>
          </li>
        ))}
      </ul>
      <label className="rv-check">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        {t(
          'I own this phone and consent to exporting the selected stores',
          'Я владелец телефона и согласен на экспорт выбранных хранилищ',
        )}
      </label>
      <button
        type="button"
        className="k-btn k-btn--primary"
        disabled={!device || !consent || picked.length === 0 || exp.isPending}
        onClick={() => exp.mutate()}
      >
        {t('Export selected', 'Экспортировать выбранное')}
      </button>
      {(exp.error || dl.error || prev.error || apply.error) && (
        <ErrorMessage error={exp.error ?? dl.error ?? prev.error ?? apply.error} />
      )}

      <h3>{t('Saved exports', 'Сохранённые экспорты')}</h3>
      {s.backups.length === 0 ? (
        <p className="k-note-line">
          {t('No settings exports yet.', 'Экспортов настроек пока нет.')}
        </p>
      ) : (
        <ul className="k-list" data-testid="settings-backups">
          {s.backups.map((b) => (
            <li key={b.id} data-backup={b.id}>
              <span>
                {b.created.slice(0, 16)} · {b.device.model ?? '?'} {b.device.rm ?? ''} ·{' '}
                {Object.entries(b.categories)
                  .map(([k, v]) => `${k}: ${v.count}`)
                  .join(', ')}
              </span>
              <span className="rv-record-inline">
                {Object.keys(b.categories)
                  .filter((k) => s.categories.find((c) => c.id === k)?.restore)
                  .map((k) => (
                    <button
                      key={k}
                      type="button"
                      className="k-btn"
                      disabled={!device || prev.isPending}
                      onClick={() => prev.mutate({ backup: b.id, category: k })}
                    >
                      {t('Preview restore', 'Предпросмотр восстановления')}:{' '}
                      {t(...(NAME[k] ?? [k, k]))}
                    </button>
                  ))}
                <button
                  type="button"
                  className="k-btn"
                  disabled={dl.isPending}
                  onClick={() => dl.mutate(b.id)}
                >
                  {t('Archive', 'Архив')}
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {dl.data && (
        <p role="status">
          {dl.data.warning}{' '}
          <Download content={dl.data.content} name={dl.data.name} mime={dl.data.mime} />
        </p>
      )}
      {preview && (
        <div
          data-testid="restore-preview"
          role="group"
          aria-label={t('Restore preview', 'Предпросмотр восстановления')}
        >
          <p>
            <strong>{preview.category}</strong> · {t('changes', 'изменений')}:{' '}
            {preview.changes.length} · {t('conflicts', 'конфликтов')}: {preview.conflicts.length}
            {preview.blocking.length > 0 &&
              ` · ${t('blocked', 'заблокировано')}: ${preview.blocking.join(', ')}`}
          </p>
          <p className="k-note-line">{st(language, preview.statement)}</p>
          {preview.other_phone && (
            <label className="rv-check">
              <input
                type="checkbox"
                checked={ackOther}
                onChange={(e) => setAckOther(e.target.checked)}
              />
              {t(
                'This backup is from another phone; restore it here anyway',
                'Копия сделана на другом телефоне; всё равно восстановить сюда',
              )}
            </label>
          )}
          <label className="rv-check">
            <input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
            {t(
              'Write this one store and verify it by reading back',
              'Записать это хранилище и проверить чтением обратно',
            )}
          </label>
          <button
            type="button"
            className="k-btn"
            disabled={
              !sure ||
              preview.conflicts.length > 0 ||
              (preview.other_phone && !ackOther) ||
              apply.isPending
            }
            onClick={() => apply.mutate(preview)}
          >
            {t('Restore', 'Восстановить')}
          </button>
        </div>
      )}
      {apply.data && (
        <p role="status" data-testid="restore-result" data-level={apply.data.level}>
          {apply.data.level}: {st(language, apply.data.statement)}
        </p>
      )}
    </SectionPanel>
  );
}
