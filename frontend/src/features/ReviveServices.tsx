import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ZodType } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { ErrorMessage } from '../components/ui';
import { SectionPanel, StatusIndicator, type Tone } from '../components/kit';
import { servicesDiagnoseSchema, servicesStateSchema, simpleSchema } from '../api/revive';
import { st } from './statements';

const TONE: Record<string, Tone> = {
  available: 'ok',
  'manual-setup-required': 'warn',
  'not-confirmed': 'unknown',
  unsupported: 'off',
};
const TEXT: Record<string, [string, string]> = {
  available: ['Available', 'Доступно'],
  'manual-setup-required': ['Needs manual setup', 'Нужна ручная настройка'],
  'not-confirmed': ['Not confirmed', 'Не подтверждено'],
  unsupported: ['Not supported', 'Не поддерживается'],
};

/** Legacy services: registry of old endpoints, per-model matrix, server-side diagnostics, your own before/after records. */
export default function ReviveServices({
  device,
  manual,
}: {
  device: string;
  manual: Record<string, string>;
}) {
  const api = useApi();
  const cache = useQueryClient();
  const { t, language } = usePreferences();
  const [pick, setPick] = useState('reborn-homepage');
  const [before, setBefore] = useState('');
  const [after, setAfter] = useState('');
  const [result, setResult] = useState('not-tested');
  const [sure, setSure] = useState(false);
  const call = <T,>(body: Record<string, unknown>, schema: ZodType<T>) =>
    api.request('/api/revive', body as never, schema);
  const state = useQuery({
    queryKey: ['revive', device, 'services', manual],
    queryFn: () => call({ action: 'services-state', device, manual }, servicesStateSchema),
    staleTime: 0,
    retry: false,
  });
  const diag = useMutation({
    mutationFn: () => call({ action: 'services-diagnose' }, servicesDiagnoseSchema),
  });
  const record = useMutation({
    mutationFn: () =>
      call(
        {
          action: 'services-record',
          device,
          manual,
          service: pick,
          before,
          after,
          result,
          confirm: true,
        },
        simpleSchema,
      ),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['revive'] }),
  });
  if (state.error) return <ErrorMessage error={state.error} />;
  if (!state.data) return null;
  const s = state.data;
  const mine = s.matrix.find((m) => m.target === s.profile);
  const rows = mine ? [mine] : s.matrix;
  const diagFor = (id: string) => diag.data?.results.find((r) => r.id === id);
  return (
    <SectionPanel title={t('Restore services', 'Восстановить сервисы')} id="revive-services">
      <p className="k-note-line">{st(language, s.statement)}</p>
      <h3>
        {mine
          ? t(`Status for ${mine.name}`, `Статус для ${mine.name}`)
          : t('Status per model', 'Статус по моделям')}
      </h3>
      <div className="rv-table-wrap">
        <table className="rv-table" data-testid="services-matrix">
          <caption className="rv-sr">
            {t('Service status per model', 'Статус сервисов по моделям')}
          </caption>
          <thead>
            <tr>
              <th scope="col">{t('Service', 'Сервис')}</th>
              {rows.map((m) => (
                <th scope="col" key={m.target}>
                  {m.name}
                </th>
              ))}
              <th scope="col">{t('Substitute', 'Заменитель')}</th>
              <th scope="col">{t('Server check', 'Проверка сервера')}</th>
            </tr>
          </thead>
          <tbody>
            {s.services.map((svc) => (
              <tr key={svc.id} data-service={svc.id}>
                <th scope="row">
                  {t(svc.title.en, svc.title.ru)}
                  <small>
                    {svc.original_url ??
                      (svc.original_url_note
                        ? t(
                            'original URL: not stated by the source',
                            'исходный URL: источник не указывает',
                          )
                        : '')}
                  </small>
                </th>
                {rows.map((m) => {
                  const cell = m.services[svc.id];
                  return (
                    <td key={m.target} data-status={cell?.status}>
                      {cell && (
                        <>
                          <StatusIndicator tone={TONE[cell.status] ?? 'unknown'}>
                            {t(...(TEXT[cell.status] ?? [cell.status, cell.status]))}
                          </StatusIndicator>
                          <small>{t(cell.reason.en, cell.reason.ru)}</small>
                        </>
                      )}
                    </td>
                  );
                })}
                <td>
                  {svc.substitute ? (
                    <>
                      <span className="rv-hash">
                        {svc.substitute.final_url ?? t('target unknown', 'цель неизвестна')}
                      </span>
                      <small>
                        {t('trust', 'доверие')}: {svc.substitute.trust}
                      </small>
                    </>
                  ) : (
                    '—'
                  )}
                </td>
                <td data-diag={svc.id}>
                  {diagFor(svc.id)
                    ? `${diagFor(svc.id)?.status}${diagFor(svc.id)?.reason ? ` (${diagFor(svc.id)?.reason})` : ''}`
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="k-toolbar">
        <button
          type="button"
          className="k-btn k-btn--primary"
          disabled={diag.isPending}
          onClick={() => diag.mutate()}
        >
          {t('Check substitute hosts (from the server)', 'Проверить хосты-заменители (с сервера)')}
        </button>
      </div>
      {diag.error && <ErrorMessage error={diag.error} />}
      {diag.data && (
        <p role="status" data-testid="services-diag">
          {t('Ran on the', 'Выполнено на')} {diag.data.ran_on}. {st(language, diag.data.statement)}
        </p>
      )}
      <p className="k-note-line">
        {t('Self-hosted bridge', 'Собственный мост')}: {s.bridge.status} — {s.bridge.note}
      </p>

      <h3>
        {t('Record a setting you changed yourself', 'Запишите настройку, которую вы изменили сами')}
      </h3>
      <form
        className="rv-form"
        onSubmit={(e) => {
          e.preventDefault();
          record.mutate();
          setSure(false);
        }}
      >
        <label>
          {t('Service', 'Сервис')}
          <select value={pick} onChange={(e) => setPick(e.target.value)}>
            {s.services
              .filter((x) => x.origin.kind !== 'none')
              .map((x) => (
                <option key={x.id} value={x.id}>
                  {t(x.title.en, x.title.ru)}
                </option>
              ))}
          </select>
        </label>
        <label>
          {t('Value before', 'Значение до')}
          <input value={before} maxLength={300} onChange={(e) => setBefore(e.target.value)} />
        </label>
        <label>
          {t('Value after', 'Значение после')}
          <input value={after} maxLength={300} onChange={(e) => setAfter(e.target.value)} />
        </label>
        <label>
          {t('Test on the phone', 'Проверка на телефоне')}
          <select value={result} onChange={(e) => setResult(e.target.value)}>
            <option value="not-tested">{t('Not tested', 'Не проверялось')}</option>
            <option value="pass">{t('It works on the phone', 'Работает на телефоне')}</option>
            <option value="fail">{t('It does not work', 'Не работает')}</option>
          </select>
        </label>
        <label className="rv-check">
          <input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
          {t(
            'I changed this setting myself on the phone',
            'Я сам изменил эту настройку на телефоне',
          )}
        </label>
        <button type="submit" className="k-btn" disabled={!sure || !device || record.isPending}>
          {t('Record', 'Записать')}
        </button>
      </form>
      {record.error && <ErrorMessage error={record.error} />}
      <ul className="k-list" data-testid="services-records">
        {s.services
          .filter((x) => x.record)
          .map((x) => (
            <li key={x.id}>
              <span>
                {t(x.title.en, x.title.ru)} — {x.record?.result}
              </span>
              <small>{x.record ? t(x.record.restore.en, x.record.restore.ru) : ''}</small>
            </li>
          ))}
      </ul>
    </SectionPanel>
  );
}
