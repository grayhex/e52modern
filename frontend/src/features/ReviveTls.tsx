import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ZodType } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { ErrorMessage } from '../components/ui';
import { SectionPanel, StatusIndicator, type Tone } from '../components/kit';
import { encode } from '../utils/files';
import ReviveSafety from './ReviveSafety';
import { safetyPlanSchema } from '../api/revive';
import {
  simpleSchema,
  tlsDiagnoseSchema,
  tlsKitSchema,
  tlsStateSchema,
  type ReviveStatus,
} from '../api/revive';

const CELL_TONE: Record<string, Tone> = {
  documented: 'info',
  'not-applicable': 'off',
  unknown: 'unknown',
};
const CELL_TEXT: Record<string, [string, string]> = {
  documented: ['Documented by author · not tested', 'Указано автором · не проверено'],
  'not-applicable': ['Not applicable', 'Не применимо'],
  unknown: ['Unknown', 'Неизвестно'],
};
const STATE_TEXT: Record<string, [string, string]> = {
  unknown: ['Unknown', 'Неизвестно'],
  'transferred-awaiting-install': [
    'Transferred, awaiting manual install',
    'Передано, ждёт ручной установки',
  ],
  'installed-reported': ['Installed (reported by you)', 'Установлено (по вашим словам)'],
  'not-installed-reported': ['Not installed (reported by you)', 'Не установлено (по вашим словам)'],
  'failed-reported': ['Failed (reported by you)', 'Не удалось (по вашим словам)'],
  'not-tested': ['Not tested', 'Не проверялось'],
};
const STATE_TONE: Record<string, Tone> = {
  unknown: 'unknown',
  'transferred-awaiting-install': 'warn',
  'installed-reported': 'info',
  'not-installed-reported': 'off',
  'failed-reported': 'bad',
  'not-tested': 'unknown',
};
const TONE: Record<ReviveStatus, Tone> = {
  ready: 'ok',
  'needs-action': 'warn',
  unknown: 'unknown',
  unsupported: 'off',
};

function mib(n: number) {
  return n >= 1024 * 1024
    ? `${(n / (1024 * 1024)).toFixed(2)} MiB`
    : `${(n / 1024).toFixed(1)} KiB`;
}

/** Symbian TLS / CA revival: applicability, pinned components, read-only diagnostics, preparation kits. */
export default function ReviveTls({
  device,
  manual,
}: {
  device: string;
  manual: Record<string, string>;
}) {
  const api = useApi();
  const cache = useQueryClient();
  const { t } = usePreferences();
  const [appKind, setAppKind] = useState('native-system');
  const [host, setHost] = useState('example.com');
  const [phoneDate, setPhoneDate] = useState('');
  const [planId, setPlanId] = useState('');
  const [sawIt, setSawIt] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const [importFor, setImportFor] = useState('');
  const call = <T,>(body: Record<string, unknown>, schema: ZodType<T>) =>
    api.request('/api/revive', body as never, schema);
  const root = ['revive', device, 'tls'] as const;
  const state = useQuery({
    queryKey: [...root, 'state'],
    queryFn: () => call({ action: 'tls-state', device, manual }, tlsStateSchema),
    staleTime: 0,
    retry: false,
  });
  const components = state.data?.components.map((c) => c.id) ?? [];
  const kit = useQuery({
    queryKey: [...root, 'kit', appKind, manual, components.join()],
    queryFn: () =>
      call(
        { action: 'tls-kit', device, manual, components: ['ssl-patch'], app_kind: appKind },
        tlsKitSchema,
      ),
    enabled: components.includes('ssl-patch'),
    staleTime: 0,
    retry: false,
  });
  const refresh = () => cache.invalidateQueries({ queryKey: ['revive'] });
  const act = useMutation({
    mutationFn: (body: Record<string, unknown>) => call({ device, manual, ...body }, simpleSchema),
    onSuccess: refresh,
  });
  const diagnose = useMutation({
    mutationFn: () =>
      call({ action: 'tls-diagnose', host, phone_date: phoneDate || undefined }, tlsDiagnoseSchema),
  });
  const plan = useMutation({
    mutationFn: (comps: string[]) =>
      call(
        { action: 'safety-plan', scenario: 'tls', device, manual, components: comps },
        safetyPlanSchema,
      ),
    onSuccess: (p) => setPlanId(p.id),
  });
  const upload = useMutation({
    mutationFn: async (picked: File) =>
      call(
        { action: 'tls-import', name: picked.name, content: await encode(picked) },
        simpleSchema,
      ),
    onSuccess: refresh,
  });

  if (state.error) return <ErrorMessage error={state.error} />;
  if (!state.data) return null;
  const data = state.data;
  const support = kit.data?.stack_support;

  return (
    <SectionPanel
      title={t('Symbian TLS / CA revival', 'Возрождение TLS / CA для Symbian')}
      id="revive-tls"
      className="rv-tls"
    >
      <p className="k-note-line">{data.statement}</p>

      <h3>{t('Applicability by model and stack', 'Применимость по моделям и стекам')}</h3>
      <div className="rv-table-wrap">
        <table className="rv-table">
          <caption className="rv-sr">
            {t('TLS stacks by phone model', 'TLS-стеки по моделям телефонов')}
          </caption>
          <thead>
            <tr>
              <th scope="col">{t('Model', 'Модель')}</th>
              {Object.entries(data.stacks).map(([id, s]) => (
                <th scope="col" key={id}>
                  {t(s.title.en, s.title.ru)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.applicability.map((r) => (
              <tr key={r.target} data-target={r.target}>
                <th scope="row">
                  {r.name}
                  <small>
                    S60 {r.s60} · Symbian {r.symbian ?? '?'}
                  </small>
                </th>
                {Object.keys(data.stacks).map((id) => {
                  const cell = r.stacks[id];
                  return (
                    <td key={id}>
                      {cell && (
                        <StatusIndicator tone={CELL_TONE[cell.status] ?? 'unknown'}>
                          {t(...(CELL_TEXT[cell.status] ?? [cell.status, cell.status]))}
                        </StatusIndicator>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="k-note-line">
        {t(
          'The author does not state firmware versions or the ROMPatcher patch version. SIS is unsigned: it needs the InstallServer patch; extraction to C: needs Open4All.',
          'Автор не указывает версии прошивок и версию патчей ROMPatcher. SIS не подписан: нужен патч InstallServer; для распаковки в C: нужен Open4All.',
        )}
      </p>

      <h3>{t('Which stack serves the application', 'Какой стек обслуживает приложение')}</h3>
      <label className="rv-inline">
        {t('Application type', 'Тип приложения')}
        <select value={appKind} onChange={(e) => setAppKind(e.target.value)}>
          {Object.entries(data.app_kinds).map(([id, k]) => (
            <option key={id} value={id}>
              {t(k.title.en, k.title.ru)}
            </option>
          ))}
        </select>
      </label>
      <p role="status" className="rv-stack-support" data-support={support?.status ?? 'unknown'}>
        {!device
          ? t(
              'Select a connection to see support for the identified model.',
              'Выберите подключение, чтобы увидеть поддержку для определённой модели.',
            )
          : support?.reason
            ? t(support.reason.en, support.reason.ru)
            : support
              ? `${t(...(CELL_TEXT[support.status] ?? ['', '']))}${support.covered_by ? ' · ' + t('via', 'через') + ' ' + support.covered_by : ''}`
              : t('Not available', 'Недоступно')}
      </p>

      <h3>{t('Pinned components', 'Закреплённые компоненты')}</h3>
      <ul className="rv-ops">
        {data.components.map((c) => (
          <li key={c.id} className="rv-op" data-component={c.id}>
            <div className="rv-op-head">
              <strong>
                {t(c.title.en, c.title.ru)} v{c.version}
              </strong>
              <StatusIndicator tone={STATE_TONE[c.device.state] ?? 'unknown'}>
                {t(...(STATE_TEXT[c.device.state] ?? [c.device.state, c.device.state]))}
              </StatusIndicator>
            </div>
            <dl className="rv-op-meta">
              <div>
                <dt>{t('Author', 'Автор')}</dt>
                <dd>
                  <a className="k-link" href={c.homepage} rel="noreferrer noopener" target="_blank">
                    {c.author}
                  </a>
                </dd>
              </div>
              <div>
                <dt>{t('Licence', 'Лицензия')}</dt>
                <dd>
                  <a
                    className="k-link"
                    href={c.licence.url}
                    rel="noreferrer noopener"
                    target="_blank"
                  >
                    {c.licence.spdx}
                  </a>
                </dd>
              </div>
              <div>
                <dt>SHA-256</dt>
                <dd className="rv-hash">{c.sha256}</dd>
              </div>
              <div>
                <dt>{t('Size', 'Размер')}</dt>
                <dd>{mib(c.size)}</dd>
              </div>
              <div>
                <dt>{t('Risk', 'Риск')}</dt>
                <dd>{c.risk}</dd>
              </div>
              <div>
                <dt>{t('File obtained', 'Файл получен')}</dt>
                <dd>{c.cached ? t('yes, verified', 'да, проверен') : t('no', 'нет')}</dd>
              </div>
            </dl>
            <p className="k-note-line">{c.release_notes_text}</p>
            <p className="k-note-line">
              {t('Pin observed', 'Закрепление снято')}: {c.observed_at}. {c.licence.note}
            </p>
            <div className="k-toolbar">
              <button
                type="button"
                className="k-btn"
                disabled={act.isPending}
                onClick={() => act.mutate({ action: 'tls-fetch', component: c.id })}
              >
                {t('Download pinned build', 'Скачать закреплённую сборку')}
              </button>
              <button
                type="button"
                className="k-btn"
                onClick={() => {
                  setImportFor(c.id);
                  file.current?.click();
                }}
              >
                {t('Import file', 'Импортировать файл')}
              </button>
            </div>
          </li>
        ))}
      </ul>
      <div className="k-toolbar">
        {(
          [
            [
              ['mbedtls-lib'],
              'Plan safe copy: MBedTLS',
              'Запланировать безопасное копирование: MBedTLS',
            ],
            [
              ['ssl-patch'],
              'Plan safe copy: System SSL patch + MBedTLS',
              'Запланировать безопасное копирование: патч SSL + MBedTLS',
            ],
          ] as const
        ).map(([comps, en, ru]) => (
          <button
            key={comps.join()}
            type="button"
            className="k-btn k-btn--primary"
            disabled={!device || plan.isPending}
            onClick={() => plan.mutate([...comps])}
          >
            {t(en, ru)}
          </button>
        ))}
      </div>
      {plan.error && <ErrorMessage error={plan.error} />}
      <input
        ref={file}
        type="file"
        hidden
        aria-label={t('Component file', 'Файл компонента')}
        onChange={(e) => {
          const picked = e.target.files?.[0];
          if (picked && importFor) upload.mutate(picked);
          e.target.value = '';
        }}
      />
      {(act.error || upload.error) && <ErrorMessage error={act.error ?? upload.error} />}
      {upload.data && (
        <p role="status">
          {t('Imported and verified against the pin.', 'Импортировано и сверено с закреплением.')}
        </p>
      )}

      {kit.data && (
        <>
          <h3>{t('Preparation kit and guide', 'Набор подготовки и инструкция')}</h3>
          <ol className="rv-kit">
            {kit.data.steps.map((s) => (
              <li key={s.id} data-step={s.id}>
                <strong>{t(s.title.en, s.title.ru)}</strong>{' '}
                <StatusIndicator tone={TONE[s.transfer.status]}>
                  {t('Copy', 'Копирование')}: {s.transfer.status}
                </StatusIndicator>
                <ol>
                  {s.install.steps.map((g, i) => (
                    <li key={i}>{t(g.en, g.ru)}</li>
                  ))}
                </ol>
                <p className="k-note-line">
                  {t('How to restore', 'Как вернуть как было')}: {t(s.restore.en, s.restore.ru)}
                </p>
                {s.high_risk && (
                  <div
                    className="rv-high-risk"
                    role="group"
                    aria-label={t('High-risk scenario', 'Сценарий высокого риска')}
                  >
                    <StatusIndicator tone={s.high_risk.status === 'ready' ? 'warn' : 'bad'}>
                      {t(
                        'High risk: system file replacement',
                        'Высокий риск: замена системного файла',
                      )}
                    </StatusIndicator>
                    <p>{t(s.high_risk.statement.en, s.high_risk.statement.ru)}</p>
                    {s.high_risk.requirements.length > 0 && (
                      <ul>
                        {s.high_risk.requirements.map((r, i) => (
                          <li key={i}>{t(r.en, r.ru)}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ol>
          <div className="rv-record">
            <label className="rv-check">
              <input type="checkbox" checked={sawIt} onChange={(e) => setSawIt(e.target.checked)} />
              {t('These are my own observations on the phone', 'Это мои наблюдения на телефоне')}
            </label>
            <div className="k-toolbar">
              {(['mbedtls-lib', 'ssl-patch'] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  className="k-btn"
                  disabled={!sawIt || !device || act.isPending}
                  onClick={() =>
                    act.mutate({ action: 'tls-record', item, state: 'installed', confirm: true })
                  }
                >
                  {t(`I installed ${item}`, `Я установил ${item}`)}
                </button>
              ))}
              <button
                type="button"
                className="k-btn"
                disabled={!sawIt || !device || act.isPending}
                onClick={() =>
                  act.mutate({
                    action: 'tls-record',
                    item: 'ssl-original-backup',
                    state: 'installed',
                    confirm: true,
                  })
                }
              >
                {t('I saved the original ssl.dll', 'Я сохранил оригинальный ssl.dll')}
              </button>
            </div>
          </div>
        </>
      )}

      <ReviveSafety device={device} planId={planId} onSelect={setPlanId} />

      <h3>{t('Read-only diagnostics', 'Диагностика (только чтение)')}</h3>
      <form
        className="rv-form"
        onSubmit={(e) => {
          e.preventDefault();
          diagnose.mutate();
        }}
      >
        <label>
          {t('Test host', 'Тестовый узел')}
          <input list="rv-hosts" value={host} onChange={(e) => setHost(e.target.value)} />
          <datalist id="rv-hosts">
            {data.test_hosts.map((h) => (
              <option key={h} value={h} />
            ))}
          </datalist>
        </label>
        <label>
          {t('Date shown on the phone (typed by you)', 'Дата на телефоне (введена вами)')}
          <input type="date" value={phoneDate} onChange={(e) => setPhoneDate(e.target.value)} />
        </label>
        <button type="submit" className="k-btn k-btn--primary" disabled={diagnose.isPending}>
          {t('Run diagnostics', 'Запустить диагностику')}
        </button>
      </form>
      {diagnose.error && <ErrorMessage error={diagnose.error} />}
      {diagnose.data && (
        <ul className="k-list rv-diagnose" data-testid="tls-diagnose">
          <li>
            <span>
              <strong>{t('Ran on the SymPort server', 'Выполнено на сервере SymPort')}</strong>
              <br />
              {diagnose.data.server_probe.ok
                ? `${diagnose.data.server_probe.tls_version ?? 'TLS'} · ${diagnose.data.server_probe.leaf?.subject ?? ''}`
                : `${t('Failed', 'Ошибка')}: ${diagnose.data.server_probe.error ?? ''}`}
              <br />
              <small>{diagnose.data.server_probe.meaning}</small>
            </span>
            <StatusIndicator tone={diagnose.data.server_probe.ok ? 'ok' : 'warn'}>
              {diagnose.data.server_probe.ok ? 'OK' : '!'}
            </StatusIndicator>
          </li>
          <li>
            <span>
              <strong>{t('Ran in the Windows Bridge', 'Выполнено в Windows Bridge')}</strong>
              <br />
              <small>{diagnose.data.bridge_probe.reason}</small>
            </span>
            <StatusIndicator tone="unknown">{t('Not available', 'Недоступно')}</StatusIndicator>
          </li>
          <li>
            <span>
              <strong>{t('Phone clock (typed by you)', 'Часы телефона (ввод вручную)')}</strong>
              <br />
              {diagnose.data.clock.phone_date
                ? `${diagnose.data.clock.phone_date} · Δ ${diagnose.data.clock.skew_days} ${t('days', 'дн.')}${diagnose.data.clock.certificate_window === 'phone-date-outside' ? ' · ' + t('outside the certificate validity window', 'вне срока действия сертификата') : ''}`
                : t('No date entered', 'Дата не введена')}
            </span>
            <StatusIndicator
              tone={
                diagnose.data.clock.verdict === 'ok'
                  ? 'ok'
                  : diagnose.data.clock.verdict === 'needs-action'
                    ? 'warn'
                    : 'unknown'
              }
            >
              {diagnose.data.clock.verdict}
            </StatusIndicator>
          </li>
          <li>
            <span>
              <strong>{t('Ran on the phone', 'Выполняется на телефоне')}</strong>
              <br />
              {t(
                diagnose.data.phone_test.instructions.en,
                diagnose.data.phone_test.instructions.ru,
              )}
              <br />
              <small>{diagnose.data.chain.reason}</small>
            </span>
            <span className="rv-record-inline">
              {(['pass', 'fail'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  className="k-btn"
                  disabled={!device || act.isPending}
                  onClick={() =>
                    act.mutate({
                      action: 'tls-record',
                      item: 'https-test',
                      state: r,
                      host,
                      confirm: true,
                    })
                  }
                >
                  {r === 'pass' ? t('It opened', 'Открылось') : t('It failed', 'Не открылось')}
                </button>
              ))}
            </span>
          </li>
        </ul>
      )}
      <p className="k-note-line">
        {t('HTTPS test on the phone', 'HTTPS-проверка на телефоне')}:{' '}
        {t(...(STATE_TEXT[data.https.state] ?? [data.https.state, data.https.state]))}
        {data.https.state === 'pass' || data.https.state === 'fail'
          ? ` (${t('typed by you', 'введено вами')})`
          : ''}
      </p>
    </SectionPanel>
  );
}
