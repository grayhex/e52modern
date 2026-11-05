import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ZodType } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { ErrorMessage } from '../components/ui';
import { SectionPanel, StatusIndicator, type Tone } from '../components/kit';
import ReviveSafety from './ReviveSafety';
import { addonPlanSchema, addonsStateSchema, safetyPlanSchema, simpleSchema } from '../api/revive';

const DECISION: Record<string, [string, string, Tone]> = {
  blocked: ['Blocked', 'Заблокировано', 'bad'],
  'manual-only': ['Manual instructions only', 'Только ручная инструкция', 'warn'],
  'ready-to-prepare': [
    'Can be prepared (copy only)',
    'Можно подготовить (только копирование)',
    'info',
  ],
};
const LEVEL = [
  'downloaded',
  'transferred',
  'user-confirmed-installed',
  'verified-on-device',
] as const;
const LEVEL_TEXT: Record<string, [string, string]> = {
  downloaded: ['Downloaded', 'Загружено'],
  transferred: ['Transferred', 'Передано'],
  'user-confirmed-installed': ['Installed (you confirmed)', 'Установлено (вы подтвердили)'],
  'verified-on-device': ['Verified on device', 'Проверено на устройстве'],
};

/** Add-ons & Patch Manager: gated dry-run plans, closed system patches, an inventory you type in. */
export default function ReviveAddons({
  device,
  manual,
}: {
  device: string;
  manual: Record<string, string>;
}) {
  const api = useApi();
  const cache = useQueryClient();
  const { t } = usePreferences();
  const [planned, setPlanned] = useState<{ id: string; text: string } | null>(null);
  const [planId, setPlanId] = useState('');
  const [sure, setSure] = useState(false);
  const [patch, setPatch] = useState({ name: '', source: '', state: 'unknown', autostart_via: '' });
  const call = <T,>(body: Record<string, unknown>, schema: ZodType<T>) =>
    api.request('/api/revive', body as never, schema);
  const state = useQuery({
    queryKey: ['revive', device, 'addons', manual],
    queryFn: () => call({ action: 'addons-state', device, manual }, addonsStateSchema),
    staleTime: 0,
    retry: false,
  });
  const refresh = () => cache.invalidateQueries({ queryKey: ['revive'] });
  const act = useMutation({
    mutationFn: (body: Record<string, unknown>) => call({ device, manual, ...body }, simpleSchema),
    onSuccess: refresh,
  });
  const dry = useMutation({
    mutationFn: ({ addon, kind }: { addon: string; kind: string }) =>
      call({ action: 'addons-plan', device, manual, addon, action_kind: kind }, addonPlanSchema),
    onSuccess: (r) =>
      setPlanned({
        id: r.addon,
        text: `${r.action}: ${r.decision}${r.blocks.length ? ' — ' + r.blocks.map((b) => b.code).join(', ') : ''}`,
      }),
  });
  const prepare = useMutation({
    mutationFn: (addon: string) =>
      call({ action: 'addons-prepare', device, manual, addon }, safetyPlanSchema),
    onSuccess: (p) => setPlanId(p.id),
  });
  if (state.error) return <ErrorMessage error={state.error} />;
  if (!state.data) return null;
  const s = state.data;
  return (
    <SectionPanel title={t('Add-ons and patches', 'Дополнения и патчи')} id="revive-addons">
      <p className="k-note-line">{s.statement}</p>
      <div className="k-toolbar">
        {Object.entries(s.categories)
          .filter(([, c]) => c.closed_by_default)
          .map(([id, c]) => (
            <span key={id} className="rv-record-inline">
              <StatusIndicator tone={c.open ? 'warn' : 'off'}>
                {t(c.title.en, c.title.ru)}:{' '}
                {c.open ? t('open', 'открыта') : t('closed', 'закрыта')}
              </StatusIndicator>
              {!c.open && (
                <>
                  <label className="rv-check">
                    <input
                      type="checkbox"
                      checked={sure}
                      onChange={(e) => setSure(e.target.checked)}
                    />
                    {t(
                      'I understand SymPort only gives instructions for system patches',
                      'Понимаю, что для системных патчей SymPort даёт только инструкции',
                    )}
                  </label>
                  <button
                    type="button"
                    className="k-btn"
                    disabled={!sure || !device || act.isPending}
                    onClick={() =>
                      act.mutate({
                        action: 'addons-open-category',
                        category: id,
                        confirm: true,
                        acknowledge: true,
                      })
                    }
                  >
                    {t('Open category', 'Открыть категорию')}
                  </button>
                </>
              )}
            </span>
          ))}
      </div>
      {act.error && <ErrorMessage error={act.error} />}
      <ul className="rv-ops">
        {s.addons.map((a) => (
          <li
            key={a.id}
            className="rv-op"
            data-addon={a.id}
            data-decision={a.decision?.decision ?? 'none'}
          >
            <div className="rv-op-head">
              <strong>{t(a.title.en, a.title.ru)}</strong>
              {a.decision ? (
                <StatusIndicator tone={DECISION[a.decision.decision]?.[2] ?? 'unknown'}>
                  {t(
                    DECISION[a.decision.decision]?.[0] ?? '',
                    DECISION[a.decision.decision]?.[1] ?? '',
                  )}
                </StatusIndicator>
              ) : (
                <StatusIndicator tone="unknown">
                  {t('Select a phone', 'Выберите телефон')}
                </StatusIndicator>
              )}
            </div>
            <dl className="rv-op-meta">
              <div>
                <dt>{t('Risk', 'Риск')}</dt>
                <dd>{a.risk}</dd>
              </div>
              <div>
                <dt>{t('Author', 'Автор')}</dt>
                <dd>
                  <a
                    className="k-link"
                    href={a.source.url}
                    rel="noreferrer noopener"
                    target="_blank"
                  >
                    {a.source.author}
                  </a>
                </dd>
              </div>
              <div>
                <dt>{t('Licence', 'Лицензия')}</dt>
                <dd>{a.licence.spdx ?? a.licence.status ?? t('unconfirmed', 'не подтверждена')}</dd>
              </div>
              <div>
                <dt>{t('Version', 'Версия')}</dt>
                <dd>
                  {a.version ?? t('none', 'нет')}{' '}
                  {a.version_confirmed ? '' : `(${t('unconfirmed', 'не подтверждена')})`}
                </dd>
              </div>
              <div>
                <dt>{t('Mode', 'Режим')}</dt>
                <dd>
                  {a.mode === 'pinned-artifact'
                    ? t('pinned artifact', 'закреплённый артефакт')
                    : t('manual only', 'только вручную')}
                </dd>
              </div>
            </dl>
            <ul className="rv-levels" data-testid={`levels-${a.id}`}>
              {LEVEL.map((k) => {
                const v = a.levels[k];
                const on = v === true;
                return (
                  <li key={k} className={`rv-chip ${on ? 'rv-chip--ok' : ''}`}>
                    {t(LEVEL_TEXT[k]?.[0] ?? k, LEVEL_TEXT[k]?.[1] ?? k)}:{' '}
                    {typeof v === 'string'
                      ? t('not available (no agent)', 'недоступно (нет агента)')
                      : on
                        ? t('yes', 'да')
                        : t('no', 'нет')}
                  </li>
                );
              })}
            </ul>
            {a.update_available && (
              <p className="k-note-line" role="status">
                {t(
                  'A newer pinned version exists: prepare it as a separate entry; nothing is written silently.',
                  'Есть более новая закреплённая версия: подготовьте её отдельной записью; ничего не пишется молча.',
                )}
              </p>
            )}
            {a.decision && a.decision.blocks.length > 0 && (
              <ul className="rv-blocks">
                {a.decision.blocks.map((b) => (
                  <li key={b.code} data-block={b.code}>
                    {t(b.text.en, b.text.ru)}
                  </li>
                ))}
              </ul>
            )}
            <p className="k-note-line">{t(a.install.en, a.install.ru)}</p>
            <p className="k-note-line">
              {t('Uninstall / rollback', 'Удаление / откат')}: {t(a.uninstall.en, a.uninstall.ru)}
            </p>
            <div className="k-toolbar">
              <button
                type="button"
                className="k-btn"
                disabled={!device || dry.isPending}
                onClick={() => dry.mutate({ addon: a.id, kind: 'install' })}
              >
                {t('Dry run', 'Пробный прогон')}
              </button>
              <button
                type="button"
                className="k-btn"
                disabled={!device || dry.isPending}
                onClick={() => dry.mutate({ addon: a.id, kind: 'remove' })}
              >
                {t('Removal plan', 'План удаления')}
              </button>
              <button
                type="button"
                className="k-btn k-btn--primary"
                disabled={a.decision?.decision !== 'ready-to-prepare' || prepare.isPending}
                onClick={() => prepare.mutate(a.id)}
              >
                {t('Prepare safe copy', 'Подготовить безопасное копирование')}
              </button>
              <button
                type="button"
                className="k-btn"
                disabled={!device || act.isPending}
                onClick={() =>
                  act.mutate({
                    action: 'addons-mark',
                    addon: a.id,
                    state: 'installed',
                    confirm: true,
                  })
                }
              >
                {t('I installed it on the phone', 'Я установил это на телефоне')}
              </button>
            </div>
            {planned?.id === a.id && (
              <p role="status" data-testid={`plan-${a.id}`}>
                {planned.text}
              </p>
            )}
          </li>
        ))}
      </ul>
      {(dry.error || prepare.error) && <ErrorMessage error={dry.error ?? prepare.error} />}
      <ReviveSafety device={device} planId={planId} onSelect={setPlanId} />

      <h3>
        {t('Patch Manager (read-only for the phone)', 'Patch Manager (только чтение для телефона)')}
      </h3>
      <p className="k-note-line" data-testid="patch-note">
        {s.patch_manager.note}
      </p>
      <form
        className="rv-form"
        onSubmit={(e) => {
          e.preventDefault();
          act.mutate({ action: 'patch-save', ...patch });
          setPatch({ name: '', source: '', state: 'unknown', autostart_via: '' });
        }}
      >
        <label>
          {t('Patch name', 'Название патча')}
          <input
            value={patch.name}
            maxLength={80}
            onChange={(e) => setPatch({ ...patch, name: e.target.value })}
          />
        </label>
        <label>
          {t('Source', 'Источник')}
          <input
            value={patch.source}
            maxLength={200}
            onChange={(e) => setPatch({ ...patch, source: e.target.value })}
          />
        </label>
        <label>
          {t('State you observed', 'Наблюдаемое состояние')}
          <select
            value={patch.state}
            onChange={(e) => setPatch({ ...patch, state: e.target.value })}
          >
            {['applied', 'disabled', 'autostart', 'unknown'].map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('Starts via (e.g. domainsrv)', 'Запускается через (например domainsrv)')}
          <input
            value={patch.autostart_via}
            maxLength={40}
            onChange={(e) => setPatch({ ...patch, autostart_via: e.target.value })}
          />
        </label>
        <button type="submit" className="k-btn" disabled={!patch.name || !device || act.isPending}>
          {t('Add to inventory', 'Добавить в инвентарь')}
        </button>
      </form>
      {s.patches.length === 0 ? (
        <p className="k-note-line">
          {t(
            'The inventory is empty. SymPort cannot read patches from the phone.',
            'Инвентарь пуст. SymPort не может прочитать патчи с телефона.',
          )}
        </p>
      ) : (
        <ul className="k-list" data-testid="patch-list">
          {s.patches.map((p) => (
            <li key={p.id} data-patch={p.name}>
              <span>
                {p.name} — {p.state}
                {p.autostart_via ? ` (${p.autostart_via})` : ''} ·{' '}
                {t('typed by you', 'введено вами')}
              </span>
              <button
                type="button"
                className="k-btn"
                onClick={() => act.mutate({ action: 'patch-delete', id: p.id, confirm: true })}
              >
                {t('Remove entry', 'Убрать запись')}
              </button>
            </li>
          ))}
        </ul>
      )}
      {s.patch_warnings.length > 0 && (
        <ul data-testid="patch-warnings" className="rv-blocks">
          {s.patch_warnings.map((w, i) => (
            <li key={i} data-warning={w.code}>
              {w.code}: {w.patch}
              {w.detail ? ` (${w.detail})` : ''}
            </li>
          ))}
        </ul>
      )}
    </SectionPanel>
  );
}
