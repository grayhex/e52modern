import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ZodType } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { ErrorMessage } from '../components/ui';
import { SectionPanel, StatusIndicator, type Tone } from '../components/kit';
import { encode } from '../utils/files';
import ReviveSafety from './ReviveSafety';
import {
  rebornImportSchema,
  rebornStageSchema,
  rebornStateSchema,
  safetyPlanSchema,
  simpleSchema,
  type ReviveStatus,
} from '../api/revive';

const TONE: Record<ReviveStatus, Tone> = {
  ready: 'ok',
  'needs-action': 'warn',
  unknown: 'unknown',
  unsupported: 'off',
};
const STAGES: [string, string, string][] = [
  ['installer-opened', 'I opened the SIS on the phone', 'Я открыл SIS на телефоне'],
  ['installed', 'The installer finished', 'Установщик завершил работу'],
  ['rebooted', 'I restarted the phone', 'Я перезагрузил телефон'],
  ['network-works', 'Network and basic functions work', 'Сеть и основные функции работают'],
];
const OUTCOME: Record<string, [string, string]> = {
  'not-confirmed': ['Installation not confirmed', 'Установка не подтверждена'],
  'installed-reported-unchecked': [
    'Installed (reported by you), network not checked',
    'Установлено (по вашим словам), сеть не проверена',
  ],
  'installed-reported': [
    'Installed and working (reported by you)',
    'Установлено и работает (по вашим словам)',
  ],
  'failed-reported': [
    'Installation failed (reported by you)',
    'Установка не удалась (по вашим словам)',
  ],
};

/** Reborn Hybrid CFW alpha for N95: a guided, honest preparation. SymPort never installs the kit. */
export default function ReviveReborn({
  device,
  manual,
}: {
  device: string;
  manual: Record<string, string>;
}) {
  const api = useApi();
  const cache = useQueryClient();
  const { t } = usePreferences();
  const file = useRef<HTMLInputElement>(null);
  const [planId, setPlanId] = useState('');
  const [sourceSure, setSourceSure] = useState(false);
  const [backupSure, setBackupSure] = useState(false);
  const [sawIt, setSawIt] = useState(false);
  const call = <T,>(body: Record<string, unknown>, schema: ZodType<T>) =>
    api.request('/api/revive', body as never, schema);
  const state = useQuery({
    queryKey: ['revive', device, 'reborn', manual],
    queryFn: () => call({ action: 'reborn-state', device, manual }, rebornStateSchema),
    staleTime: 0,
    retry: false,
  });
  const refresh = () => cache.invalidateQueries({ queryKey: ['revive'] });
  const upload = useMutation({
    mutationFn: async (picked: File) =>
      call(
        {
          action: 'reborn-import',
          device,
          manual,
          name: picked.name,
          content: await encode(picked),
        },
        rebornImportSchema,
      ),
  });
  const pin = useMutation({
    mutationFn: (sha256: string) =>
      call({ action: 'reborn-pin', sha256, confirm: true }, simpleSchema),
    onSuccess: refresh,
  });
  const backup = useMutation({
    mutationFn: () =>
      call({ action: 'reborn-backup', device, manual, confirm: true }, simpleSchema),
    onSuccess: refresh,
  });
  const plan = useMutation({
    mutationFn: (sha256: string) =>
      call(
        { action: 'safety-plan', scenario: 'reborn-n95', device, manual, sha256 },
        safetyPlanSchema,
      ),
    onSuccess: (p) => setPlanId(p.id),
  });
  const stage = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      call({ action: 'reborn-stage', device, manual, confirm: true, ...body }, rebornStageSchema),
    onSuccess: refresh,
  });

  if (state.error) return <ErrorMessage error={state.error} />;
  if (!state.data) return null;
  const s = state.data;
  const c = s.card;
  const imported = upload.data;
  const pinnedSha = s.pin?.sha256 ?? '';
  const outcomeKey = (() => {
    const st = s.stages;
    if (st['installed']?.result === 'fail') return 'failed-reported';
    if (st['installed']?.result === 'pass')
      return st['network-works']?.result === 'pass'
        ? 'installed-reported'
        : 'installed-reported-unchecked';
    return 'not-confirmed';
  })();

  return (
    <SectionPanel title={t(c.title.en, c.title.ru)} id="revive-reborn" className="rv-reborn">
      <div className="rv-high-risk" role="note">
        <StatusIndicator tone="bad">
          {t('Alpha · high risk', 'Альфа · высокий риск')}
        </StatusIndicator>
        <p>{t(c.not_a_flash.en, c.not_a_flash.ru)}</p>
        <ul>
          {c.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </div>
      <dl className="rv-op-meta">
        <div>
          <dt>{t('Author', 'Автор')}</dt>
          <dd>
            <a className="k-link" href={c.author_page} rel="noreferrer noopener" target="_blank">
              {c.author} · avalibeyaz.com/s60
            </a>
          </dd>
        </div>
        <div>
          <dt>{t('Version', 'Версия')}</dt>
          <dd>{c.version}</dd>
        </div>
        <div>
          <dt>{t('Release date', 'Дата выпуска')}</dt>
          <dd>{c.release_date ?? t('not stated by the author', 'автор не указал')}</dd>
        </div>
        <div>
          <dt>{t('Changelog', 'Список изменений')}</dt>
          <dd>{c.changelog ?? t('not published', 'не опубликован')}</dd>
        </div>
        <div>
          <dt>{t('Pinned SHA-256', 'Закреплённый SHA-256')}</dt>
          <dd className="rv-hash">
            {s.pin
              ? `${s.pin.sha256} (${t('your pin', 'ваше закрепление')})`
              : t('none: the author publishes no hash', 'нет: автор не публикует хеш')}
          </dd>
        </div>
        <div>
          <dt>{t('Distribution', 'Распространение')}</dt>
          <dd>
            {c.distribution.status} — {t(c.distribution.note.en, c.distribution.note.ru)}
          </dd>
        </div>
      </dl>
      <ul className="k-list">
        {Object.entries(c.compatibility).map(([k, v]) => (
          <li key={k}>
            <span>{k}</span>
            <span>{v}</span>
          </li>
        ))}
      </ul>

      <h3>{t('1. Preflight from the device', '1. Предполётная проверка по устройству')}</h3>
      <p role="status" data-testid="reborn-variant" data-variant={s.variant.status}>
        <StatusIndicator tone={s.variant.status === 'blocked' ? 'bad' : 'warn'}>
          {s.variant.status === 'blocked'
            ? t('Blocked', 'Заблокировано')
            : t('Unverified candidate', 'Непроверенный кандидат')}
        </StatusIndicator>{' '}
        {t(s.variant.reason.en, s.variant.reason.ru)}
      </p>
      <ul className="k-list rv-checks">
        {s.checks.map((k) => (
          <li key={k.id} data-reborn-check={k.id} data-status={k.status}>
            <span className="rv-check-text">
              <strong>{k.id}</strong>
              <span>{t(k.reason.en, k.reason.ru)}</span>
            </span>
            <StatusIndicator tone={TONE[k.status]}>{k.status}</StatusIndicator>
          </li>
        ))}
      </ul>

      <h3>
        {t(
          '2. Import the file you obtained from the author',
          '2. Импорт файла, полученного у автора',
        )}
      </h3>
      <p className="k-note-line">
        {t(
          'SymPort does not download this kit. Prerequisite (author): the installserver.exe patch must be installed.',
          'SymPort не скачивает этот набор. Условие автора: должен быть установлен патч installserver.exe.',
        )}
      </p>
      <div className="k-toolbar">
        <button type="button" className="k-btn" onClick={() => file.current?.click()}>
          {t('Import SIS', 'Импортировать SIS')}
        </button>
      </div>
      <input
        ref={file}
        type="file"
        hidden
        accept=".sis,.sisx"
        aria-label={t('Reborn SIS file', 'Файл Reborn SIS')}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) upload.mutate(f);
          e.target.value = '';
        }}
      />
      {upload.error && <ErrorMessage error={upload.error} />}
      {imported && (
        <div data-testid="reborn-import">
          <p className="rv-hash">{imported.sha256}</p>
          <ul className="k-list">
            <li>
              <span>{t('File name', 'Имя файла')}</span>
              <span>
                {imported.name}{' '}
                {imported.name_matches
                  ? ''
                  : `(${t('author name', 'у автора')}: ${imported.expected_name})`}
              </span>
            </li>
            <li>
              <span>{t('Signature', 'Подпись')}</span>
              <span>{imported.signature}</span>
            </li>
            <li>
              <span>{t('Static platform verdict', 'Статический вердикт платформы')}</span>
              <span>{imported.platform_verdict}</span>
            </li>
            <li>
              <span>{t('System-level components', 'Системные компоненты')}</span>
              <span>{imported.high_risk_count}</span>
            </li>
          </ul>
          <details open>
            <summary>{t('Content preview', 'Состав пакета')}</summary>
            <ul className="k-list">
              {imported.files.map((f) => (
                <li key={f.target} data-high-risk={f.high_risk}>
                  <span>{f.target}</span>
                  <span>{f.high_risk ? t('high risk', 'высокий риск') : ''}</span>
                </li>
              ))}
            </ul>
          </details>
          <p className="k-note-line">{imported.statement}</p>
          {imported.differs_from_pin && (
            <p role="alert">
              {t(
                'This file differs from your pinned file; transfer stays blocked until you pin this one.',
                'Файл отличается от закреплённого; копирование заблокировано, пока вы не закрепите этот.',
              )}
            </p>
          )}
          <label className="rv-check">
            <input
              type="checkbox"
              checked={sourceSure}
              onChange={(e) => setSourceSure(e.target.checked)}
            />
            {t('I obtained this exact file from the author', 'Я получил именно этот файл у автора')}
          </label>
          <button
            type="button"
            className="k-btn"
            disabled={!sourceSure || pin.isPending}
            onClick={() => pin.mutate(imported.sha256)}
          >
            {t('Pin this SHA-256', 'Закрепить этот SHA-256')}
          </button>
        </div>
      )}
      {pin.error && <ErrorMessage error={pin.error} />}

      <h3>{t('3. Your own backup', '3. Ваша собственная резервная копия')}</h3>
      <p className="k-note-line">
        {t('SymPort file backups', 'Файловые копии SymPort')}: {s.backups.count}. {s.backups.note}{' '}
        {t('A copy of the card does not restore the phone.', 'Копия карты не восстановит телефон.')}
      </p>
      <label className="rv-check">
        <input
          type="checkbox"
          checked={backupSure}
          onChange={(e) => setBackupSure(e.target.checked)}
        />
        {t(
          'I have a separate copy of the data I care about',
          'У меня есть отдельная копия важных данных',
        )}
      </label>
      <button
        type="button"
        className="k-btn"
        disabled={!backupSure || !device || backup.isPending}
        onClick={() => backup.mutate()}
      >
        {t('Record my statement', 'Записать моё подтверждение')}
      </button>
      <p className="k-note-line" data-testid="reborn-backup">
        {s.data_backup
          ? t(
              'Recorded (your statement, not verified by SymPort).',
              'Записано (ваше утверждение, SymPort его не проверял).',
            )
          : t(
              'Not recorded: the transfer stays blocked.',
              'Не записано: копирование заблокировано.',
            )}
      </p>

      <h3>{t('4. Plan the safe copy', '4. План безопасного копирования')}</h3>
      <button
        type="button"
        className="k-btn k-btn--primary"
        disabled={!device || !pinnedSha || plan.isPending}
        onClick={() => plan.mutate(pinnedSha)}
      >
        {t('Plan safe copy of the pinned file', 'Запланировать копирование закреплённого файла')}
      </button>
      {plan.error && <ErrorMessage error={plan.error} />}
      <ReviveSafety device={device} planId={planId} onSelect={setPlanId} />

      <h3>{t('5. What happened on the phone', '5. Что произошло на телефоне')}</h3>
      <p className="k-note-line">
        {t(
          'SymPort cannot see these steps; record what you observed.',
          'SymPort не видит эти шаги; запишите, что вы наблюдали.',
        )}
      </p>
      <label className="rv-check">
        <input type="checkbox" checked={sawIt} onChange={(e) => setSawIt(e.target.checked)} />
        {t('These are my own observations', 'Это мои собственные наблюдения')}
      </label>
      <ul className="k-list" data-testid="reborn-stages">
        {STAGES.map(([id, en, ru]) => (
          <li key={id} data-stage={id}>
            <span>
              {t(en, ru)}
              {s.stages[id] ? ` — ${s.stages[id].result}` : ''}
            </span>
            <span className="rv-record-inline">
              {(['pass', 'fail'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  className="k-btn"
                  disabled={!sawIt || !device || stage.isPending}
                  onClick={() => stage.mutate({ stage: id, result: r })}
                >
                  {r === 'pass' ? t('Yes', 'Да') : t('No', 'Нет')}
                </button>
              ))}
            </span>
          </li>
        ))}
      </ul>
      {stage.error && <ErrorMessage error={stage.error} />}
      <p role="status" data-testid="reborn-outcome" data-outcome={outcomeKey}>
        <StatusIndicator
          tone={
            outcomeKey === 'installed-reported'
              ? 'info'
              : outcomeKey === 'failed-reported'
                ? 'bad'
                : 'unknown'
          }
        >
          {t(...(OUTCOME[outcomeKey] ?? [outcomeKey, outcomeKey]))}
        </StatusIndicator>
      </p>
      <p className="k-note-line">{s.statement}</p>
    </SectionPanel>
  );
}
