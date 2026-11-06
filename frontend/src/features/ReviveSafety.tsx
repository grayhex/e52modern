import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ZodType } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { ErrorMessage } from '../components/ui';
import { Download } from '../components/workspace';
import { SectionPanel, StatusIndicator, type Tone } from '../components/kit';
import {
  exportSchema,
  postflightSchema,
  rollbackSchema,
  safetyPlanSchema,
  safetyStateSchema,
  simpleSchema,
} from '../api/revive';
import { st } from './statements';

const STATUS_TEXT: Record<string, [string, string, Tone]> = {
  planned: ['Planned (dry run)', 'План (пробный прогон)', 'info'],
  snapshotted: ['Snapshot taken', 'Снимок сделан', 'info'],
  applying: ['Copying', 'Копирование', 'warn'],
  interrupted: ['Interrupted — can resume', 'Прервано — можно продолжить', 'warn'],
  'transferred-awaiting-manual-install': [
    'Transferred, awaiting manual install',
    'Передано, ждёт ручной установки',
    'warn',
  ],
  'rolled-back': ['Our files removed', 'Наши файлы удалены', 'info'],
  'rollback-partial': ['Rollback partial', 'Откат частичный', 'warn'],
};
const ITEM_STATE: Record<string, [string, string]> = {
  planned: ['planned', 'запланирован'],
  written: ['written and verified', 'записан и проверен'],
  conflict: ['conflict — not overwritten', 'конфликт — не перезаписан'],
  'hash-mismatch': ['read-back mismatch', 'несовпадение при чтении'],
  'identical-preexisting': ['already there (identical)', 'уже есть (идентичен)'],
};
const CHECK_LABEL: Record<string, [string, string]> = {
  boot: ['The phone boots', 'Телефон загружается'],
  connectivity: ['Connectivity (calls / data)', 'Связь (звонки / данные)'],
  wifi: ['Wi-Fi', 'Wi-Fi'],
  files: ['Files are intact', 'Файлы на месте'],
  contacts: ['Contacts', 'Контакты'],
  apps: ['Applications start', 'Приложения запускаются'],
  https: ['HTTPS works', 'HTTPS работает'],
  errors: ['No new errors seen', 'Новых ошибок нет'],
};
function statusText(status: string, t: (en: string, ru: string) => string) {
  const entry = STATUS_TEXT[status];
  return entry ? t(entry[0], entry[1]) : status;
}
const RISK_TEXT: Record<'low' | 'medium' | 'high', [string, string]> = {
  low: ['Low risk', 'Низкий риск'],
  medium: ['Medium risk', 'Средний риск'],
  high: ['High risk', 'Высокий риск'],
} as const;

/** Recovery Safety Net: dry run → snapshot → copy → postflight → rollback of our own files → report. */
export default function ReviveSafety({
  device,
  planId,
  onSelect,
}: {
  device: string;
  planId: string;
  onSelect: (id: string) => void;
}) {
  const api = useApi();
  const cache = useQueryClient();
  const { t, language } = usePreferences();
  const [sure, setSure] = useState(false);
  const [ackSure, setAckSure] = useState(false);
  const [saw, setSaw] = useState(false);
  const call = <T,>(body: Record<string, unknown>, schema: ZodType<T>) =>
    api.request('/api/revive', body as never, schema);
  const state = useQuery({
    queryKey: ['revive', device, 'safety', 'state'],
    queryFn: () => call({ action: 'safety-state', device }, safetyStateSchema),
    staleTime: 0,
    retry: false,
  });
  const plan = useQuery({
    queryKey: ['revive', device, 'safety', 'plan', planId],
    queryFn: () => call({ action: 'safety-view', plan: planId }, safetyPlanSchema),
    enabled: Boolean(planId),
    staleTime: 0,
    retry: false,
  });
  const refresh = () => cache.invalidateQueries({ queryKey: ['revive', device, 'safety'] });
  const step = useMutation({
    mutationFn: (body: Record<string, unknown>) => call(body, safetyPlanSchema),
    onSuccess: (p) => {
      onSelect(p.id);
      void refresh();
    },
  });
  const post = useMutation({
    mutationFn: () => call({ action: 'safety-postflight', plan: planId }, postflightSchema),
  });
  const back = useMutation({
    mutationFn: (confirm: boolean) =>
      call({ action: 'safety-rollback', plan: planId, confirm }, rollbackSchema),
    onSuccess: refresh,
  });
  const report = useMutation({
    mutationFn: () => call({ action: 'safety-export', plan: planId }, exportSchema),
  });
  const check = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      call({ action: 'safety-checklist', plan: planId, confirm: true, ...body }, simpleSchema),
    onSuccess: async () => {
      await refresh();
    },
  });

  const p = plan.data ?? null;
  const error =
    step.error ??
    post.error ??
    back.error ??
    report.error ??
    check.error ??
    state.error ??
    plan.error;

  return (
    <SectionPanel
      title={t('Recovery Safety Net', 'Страховка восстановления')}
      id="revive-safety"
      className="rv-safety"
    >
      <p className="k-note-line">{st(language, state.data?.statement)}</p>
      {state.data && state.data.plans.length > 0 && (
        <ul className="k-list rv-plans" aria-label={t('Saved plans', 'Сохранённые планы')}>
          {state.data.plans.slice(0, 5).map((s) => (
            <li key={s.id} data-plan={s.id}>
              <span>
                <strong>{s.label}</strong> · {s.created.slice(0, 16)} · {s.items}{' '}
                {t('file(s)', 'файл(ов)')}
              </span>
              <span className="rv-record-inline">
                <StatusIndicator tone={STATUS_TEXT[s.status]?.[2] ?? 'unknown'}>
                  {statusText(s.status, t)}
                </StatusIndicator>
                <button type="button" className="k-btn" onClick={() => onSelect(s.id)}>
                  {t('Open', 'Открыть')}
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {!planId && (
        <p className="k-note-line">
          {t(
            'No plan selected. Plan a safe copy above.',
            'План не выбран. Запланируйте безопасное копирование выше.',
          )}
        </p>
      )}
      {error && <ErrorMessage error={error} />}
      {planId && (
        <div className="rv-plan" data-testid="safety-plan">
          {p && (
            <>
              <p>
                <strong>{p.label}</strong>{' '}
                <StatusIndicator tone={STATUS_TEXT[p.status]?.[2] ?? 'unknown'}>
                  {statusText(p.status, t)}
                </StatusIndicator>{' '}
                <StatusIndicator
                  tone={p.risk.level === 'high' ? 'bad' : p.risk.level === 'medium' ? 'warn' : 'ok'}
                >
                  {t(...RISK_TEXT[p.risk.level])}
                </StatusIndicator>
              </p>
              <h3>{t('Dry run', 'Пробный прогон')}</h3>
              <ul className="k-list">
                {p.items.map((i) => (
                  <li key={i.path} data-item={i.name}>
                    <span>
                      {i.path} · {i.size} B
                      <br />
                      <small className="rv-hash">{i.sha256}</small>
                    </span>
                    <span>{t(...(ITEM_STATE[i.state] ?? [i.state, i.state]))}</span>
                  </li>
                ))}
              </ul>
              <p className="k-note-line">
                {t('New files', 'Новых файлов')}: {p.dry_run.new_files} ·{' '}
                {t('Overwrites', 'Перезаписей')}: 0 · {t('Conflicts', 'Конфликтов')}:{' '}
                {p.dry_run.conflicts.length}. {p.dry_run.note}
              </p>
              {p.blocking.length > 0 && (
                <div
                  className="rv-high-risk"
                  role="group"
                  aria-label={t('Blocking risks', 'Блокирующие риски')}
                >
                  <strong>{t('Blocking risks', 'Блокирующие риски')}</strong>
                  <ul>
                    {p.blocking.map((b) => (
                      <li key={b.code}>{t(b.text.en, b.text.ru)}</li>
                    ))}
                  </ul>
                  {p.blocking.some((b) => b.satisfied_by === 'acknowledgement') && (
                    <>
                      <label className="rv-check">
                        <input
                          type="checkbox"
                          checked={ackSure}
                          onChange={(e) => setAckSure(e.target.checked)}
                        />
                        {t(
                          'I understand this cannot be undone by SymPort',
                          'Я понимаю, что SymPort не сможет это откатить',
                        )}
                      </label>
                      <button
                        type="button"
                        className="k-btn"
                        disabled={!ackSure || step.isPending}
                        onClick={() =>
                          step.mutate({
                            action: 'safety-ack',
                            plan: planId,
                            codes: p.blocking
                              .filter((b) => b.satisfied_by === 'acknowledgement')
                              .map((b) => b.code),
                            confirm: true,
                          })
                        }
                      >
                        {t('Acknowledge', 'Подтвердить')}
                      </button>
                    </>
                  )}
                </div>
              )}
              {p.snapshot && (
                <>
                  <h3>{t('Snapshot', 'Снимок')}</h3>
                  <ul className="k-list" data-testid="snapshot-kinds">
                    {Object.entries(p.snapshot.kinds).map(([k, v]) => (
                      <li key={k}>
                        <span>{k}</span>
                        <span>{v}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="k-note-line">{st(language, p.snapshot.statement)}</p>
                </>
              )}
              <h3>{t('Manual steps on the phone', 'Ручные шаги на телефоне')}</h3>
              <ol>
                {p.phone_actions.map((a) => (
                  <li key={a.component}>
                    <strong>{a.component}</strong>
                    <ol>
                      {a.steps.map((s, i) => (
                        <li key={i}>{t(s.en, s.ru)}</li>
                      ))}
                    </ol>
                    <small>
                      {t('Restore', 'Восстановление')}: {t(a.restore.en, a.restore.ru)}
                    </small>
                  </li>
                ))}
              </ol>
            </>
          )}
          <label className="rv-check">
            <input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
            {t('I confirm this step', 'Подтверждаю этот шаг')}
          </label>
          <div className="k-toolbar">
            <button
              type="button"
              className="k-btn"
              disabled={!sure || step.isPending}
              onClick={() => {
                step.mutate({ action: 'safety-snapshot', plan: planId, confirm: true });
                setSure(false);
              }}
            >
              {t('1. Take snapshot', '1. Сделать снимок')}
            </button>
            <button
              type="button"
              className="k-btn k-btn--primary"
              disabled={!sure || step.isPending}
              onClick={() => {
                step.mutate({ action: 'safety-apply', plan: planId, confirm: true });
                setSure(false);
              }}
            >
              {t('2. Copy files to the phone', '2. Скопировать файлы на телефон')}
            </button>
            <button
              type="button"
              className="k-btn"
              disabled={post.isPending}
              onClick={() => post.mutate()}
            >
              {t('3. Postflight (read only)', '3. Проверка после (только чтение)')}
            </button>
            <button
              type="button"
              className="k-btn"
              disabled={back.isPending}
              onClick={() => back.mutate(false)}
            >
              {t('Rollback preview', 'Предпросмотр отката')}
            </button>
            <button
              type="button"
              className="k-btn"
              disabled={!sure || back.isPending}
              onClick={() => {
                back.mutate(true);
                setSure(false);
              }}
            >
              {t('Rollback our files', 'Откатить наши файлы')}
            </button>
            <button
              type="button"
              className="k-btn"
              disabled={report.isPending}
              onClick={() => report.mutate()}
            >
              {t('Export JSON report', 'Экспорт отчёта JSON')}
            </button>
          </div>
          {back.data && (
            <p role="status" data-testid="rollback-result">
              {back.data.dry_run
                ? `${t('Would remove', 'Будет удалено')}: ${back.data.files?.length ?? 0}. `
                : `${t('Removed', 'Удалено')}: ${back.data.removed?.length ?? 0}, ${t('kept (changed)', 'оставлено (изменены)')}: ${back.data.conflicts?.length ?? 0}. `}
              {back.data.scope}
            </p>
          )}
          {post.data && (
            <div role="status" data-testid="postflight-result">
              <p>
                {t('Identity', 'Идентичность')}: {post.data.identity ?? '—'} ·{' '}
                {t('Installation', 'Установка')}: {post.data.installation ?? '—'}
              </p>
              <ul className="k-list">
                {(post.data.files ?? []).map((f) => (
                  <li key={f.path}>
                    <span>{f.path}</span>
                    <span>{f.state}</span>
                  </li>
                ))}
                {(post.data.diff ?? []).map((d) => (
                  <li key={d.field}>
                    <span>{d.field}</span>
                    <span>
                      {String(d.before)} → {String(d.after)}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="k-note-line">{st(language, post.data.statement)}</p>
            </div>
          )}
          {report.data && (
            <Download
              content={report.data.content}
              name={report.data.name}
              mime={report.data.mime}
            />
          )}
          <h3>{t('Checklist (your observations)', 'Чек-лист (ваши наблюдения)')}</h3>
          <label className="rv-check">
            <input type="checkbox" checked={saw} onChange={(e) => setSaw(e.target.checked)} />
            {t('These are what I saw on the phone', 'Это то, что я увидел на телефоне')}
          </label>
          <ul className="k-list rv-checklist">
            {(state.data?.checklist_items ?? []).map((item) => (
              <li key={item} data-check-item={item}>
                <span>
                  {t(...(CHECK_LABEL[item] ?? [item, item]))}
                  {p?.checklist[item] ? ` — ${p.checklist[item].result}` : ''}
                </span>
                <span className="rv-record-inline">
                  {(['pass', 'fail'] as const).map((r) => (
                    <button
                      key={r}
                      type="button"
                      className="k-btn"
                      disabled={!saw || check.isPending}
                      onClick={() => check.mutate({ item, result: r })}
                    >
                      {r === 'pass' ? t('OK', 'Да') : t('Problem', 'Проблема')}
                    </button>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </SectionPanel>
  );
}
