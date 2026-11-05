import { useEffect, useId, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { LifeBuoy, PlugZap } from 'lucide-react';
import { useApi, usePreferences } from '../state/app';
import { DeviceSelect, ErrorMessage } from '../components/ui';
import {
  EmptyState,
  PageHeader,
  SectionPanel,
  StatusIndicator,
  type Tone,
} from '../components/kit';
import ReviveAgent from './ReviveAgent';
import ReviveHome from './ReviveHome';
import ReviveReborn from './ReviveReborn';
import ReviveServices from './ReviveServices';
import ReviveTls from './ReviveTls';
import {
  inspectSchema,
  planSchema,
  simpleSchema,
  stateSchema,
  verifySchema,
  type Check,
  type Fact,
  type Operation,
  type ReviveStatus,
} from '../api/revive';

const STATUS_TONE: Record<ReviveStatus, Tone> = {
  ready: 'ok',
  'needs-action': 'warn',
  unknown: 'unknown',
  unsupported: 'off',
};
const STATUS_TEXT: Record<ReviveStatus, [string, string]> = {
  ready: ['Ready', 'Готово'],
  'needs-action': ['Needs action', 'Нужны действия'],
  unknown: ['Unknown', 'Неизвестно'],
  unsupported: ['Unsupported', 'Не поддерживается'],
};
const SOURCE_TEXT: Record<Fact['source'], [string, string, Tone]> = {
  observed: ['Read from the device', 'Прочитано с устройства', 'ok'],
  documented: ['Documented profile', 'Документированный профиль', 'info'],
  manual: ['Typed by you', 'Введено вами', 'warn'],
  unknown: ['Not determined', 'Не определено', 'unknown'],
};
const RISK_TEXT: Record<'low' | 'medium' | 'high', [string, string]> = {
  low: ['Low risk', 'Низкий риск'],
  medium: ['Medium risk', 'Средний риск'],
  high: ['High risk', 'Высокий риск'],
};
const EXEC_TEXT: Record<Operation['execution'], [string, string]> = {
  'read-only': ['Read only', 'Только чтение'],
  'bridge-transfer': ['File copy through the connection', 'Копирование файлов через подключение'],
  'manual-on-phone': ['You do it on the phone', 'Вы делаете это на телефоне'],
};
const RESTORE_TEXT: Record<string, [string, string]> = {
  'not-needed': ['Not needed', 'Не требуется'],
  recommended: ['Recommended before use', 'Рекомендуется перед применением'],
};
const FACT_ORDER: [string, string, string][] = [
  ['model', 'Model', 'Модель'],
  ['rm', 'RM code', 'Код RM'],
  ['product_code', 'Product code', 'Product code'],
  ['firmware', 'Firmware', 'Прошивка'],
  ['platform', 'Platform', 'Платформа'],
  ['connection', 'Connection', 'Подключение'],
  ['free', 'Free space', 'Свободно'],
  ['total', 'Total space', 'Всего'],
  ['capabilities', 'Verified operations', 'Проверенные операции'],
  ['rights', 'Installation rights', 'Права установки'],
  ['patches', 'Patches', 'Патчи'],
];

function useStatusText() {
  const { t } = usePreferences();
  return (status: ReviveStatus) => t(...STATUS_TEXT[status]);
}

function StatusBadge({ status }: { status: ReviveStatus }) {
  const label = useStatusText();
  return <StatusIndicator tone={STATUS_TONE[status]}>{label(status)}</StatusIndicator>;
}

function MiB(value: number) {
  return `${Math.round(value / (1024 * 1024)).toLocaleString()} MiB`;
}

function formatFact(id: string, fact: Fact, t: (en: string, ru: string) => string) {
  const v = fact.value;
  if (v === null || v === undefined || (Array.isArray(v) && v.length === 0))
    return t('not reported', 'не сообщено');
  if ((id === 'free' || id === 'total') && typeof v === 'number') return MiB(v);
  if (id === 'rights' && typeof v === 'string')
    return (
      {
        none: t('none', 'нет'),
        'memory-card': t('memory card only', 'только карта памяти'),
        device: t('device level', 'уровень устройства'),
      }[v] ?? v
    );
  if (id === 'capabilities' && Array.isArray(v)) return `${v.length}`;
  return Array.isArray(v) ? v.join(', ') : String(v);
}

function Facts({ facts }: { facts: Record<string, Fact> }) {
  const { t } = usePreferences();
  return (
    <dl className="rv-facts">
      {FACT_ORDER.map(([id, en, ru]) => {
        const fact = facts[id];
        if (!fact) return null;
        const [sEn, sRu, tone] = SOURCE_TEXT[fact.source];
        return (
          <div key={id} className="rv-fact" data-fact={id}>
            <dt>{t(en, ru)}</dt>
            <dd>
              <span className="rv-fact-value">{formatFact(id, fact, t)}</span>
              <StatusIndicator tone={tone}>{t(sEn, sRu)}</StatusIndicator>
              {fact.note && <small>{fact.note}</small>}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

function Checks({ checks }: { checks: Check[] }) {
  const { t } = usePreferences();
  return (
    <ul className="k-list rv-checks" aria-label={t('Readiness checks', 'Проверки готовности')}>
      {checks.map((c) => (
        <li key={c.id} data-check={c.id} data-status={c.status}>
          <span className="rv-check-text">
            <strong>{t(CHECK_EN[c.id] ?? c.id, CHECK_RU[c.id] ?? c.id)}</strong>
            <span>{t(c.reason.en, c.reason.ru)}</span>
            {c.basis !== 'none' && (
              <small>
                {t('Basis', 'Основание')}: {c.basis}
                {c.source ? ` · ${c.source}` : ''}
              </small>
            )}
          </span>
          <StatusBadge status={c.status} />
        </li>
      ))}
    </ul>
  );
}
const CHECK_EN: Record<string, string> = {
  connection: 'Connection',
  identity: 'Identity',
  platform: 'Platform',
  firmware: 'Firmware',
  storage: 'Free space',
  files: 'Files',
  transfer: 'Copying',
  restore: 'Read back',
  rights: 'Rights',
  baseline: 'Baseline',
};
const CHECK_RU: Record<string, string> = {
  connection: 'Подключение',
  identity: 'Идентификация',
  platform: 'Платформа',
  firmware: 'Прошивка',
  storage: 'Свободное место',
  files: 'Файлы',
  transfer: 'Копирование',
  restore: 'Чтение назад',
  rights: 'Права',
  baseline: 'Исходное состояние',
};

function OperationItem({
  op,
  onRecord,
  busy,
}: {
  op: Operation;
  onRecord: (operation: string, result: string, note: string) => void;
  busy: boolean;
}) {
  const { t } = usePreferences();
  const id = useId();
  const [result, setResult] = useState('done');
  const [note, setNote] = useState('');
  const [sure, setSure] = useState(false);
  const recorded = op.result.result !== 'not-run';
  return (
    <li className="rv-op" data-op={op.id} data-status={op.status}>
      <div className="rv-op-head">
        <strong>{t(op.title.en, op.title.ru)}</strong>
        <StatusBadge status={op.status} />
      </div>
      <dl className="rv-op-meta">
        <div>
          <dt>{t('Risk', 'Риск')}</dt>
          <dd>{t(...RISK_TEXT[op.risk])}</dd>
        </div>
        <div>
          <dt>{t('Method', 'Способ')}</dt>
          <dd>{t(...EXEC_TEXT[op.execution])}</dd>
        </div>
        <div>
          <dt>{t('Source', 'Источник')}</dt>
          <dd>{op.source.ref}</dd>
        </div>
        <div>
          <dt>{t('Version / SHA-256', 'Версия / SHA-256')}</dt>
          <dd>
            {op.version ?? t('none', 'нет')} / {op.sha256 ?? t('none', 'нет')}
          </dd>
        </div>
        <div>
          <dt>{t('Restore point', 'Точка восстановления')}</dt>
          <dd>{t(...(RESTORE_TEXT[op.restore_point] ?? [op.restore_point, op.restore_point]))}</dd>
        </div>
        <div>
          <dt>{t('Result', 'Результат')}</dt>
          <dd>
            {recorded
              ? `${op.result.result} (${op.result.source === 'manual' ? t('typed by you', 'введено вами') : (op.result.source ?? '')}${op.result.at ? `, ${op.result.at.slice(0, 16)}` : ''})`
              : t('not run', 'не выполнялось')}
          </dd>
        </div>
      </dl>
      {op.prerequisites.length > 0 && (
        <p className="rv-prereq">
          {t('Prerequisites', 'Условия')}:{' '}
          {op.prerequisites.map((p) => (
            <span key={p.id} className={`rv-chip rv-chip--${STATUS_TONE[p.status]}`}>
              {t(p.id, CHECK_RU[p.id] ?? p.id)}
            </span>
          ))}
        </p>
      )}
      {op.note && <p className="k-note-line">{t(op.note.en, op.note.ru)}</p>}
      {op.execution === 'manual-on-phone' && (
        <form
          className="rv-record"
          onSubmit={(event) => {
            event.preventDefault();
            onRecord(op.id, result, note);
            setSure(false);
          }}
        >
          <label htmlFor={id + 'r'}>
            {t('What happened on the phone', 'Что произошло на телефоне')}
          </label>
          <select id={id + 'r'} value={result} onChange={(e) => setResult(e.target.value)}>
            <option value="done">{t('Done, it worked', 'Выполнено, сработало')}</option>
            <option value="failed">{t('Done, it failed', 'Выполнено, не сработало')}</option>
            <option value="not-tested">{t('Not tested', 'Не проверялось')}</option>
          </select>
          <label htmlFor={id + 'n'}>{t('Note (optional)', 'Заметка (необязательно)')}</label>
          <input
            id={id + 'n'}
            value={note}
            maxLength={200}
            onChange={(e) => setNote(e.target.value)}
          />
          <label className="rv-check">
            <input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
            {t('This is what I saw on the phone', 'Это то, что я увидел на телефоне')}
          </label>
          <button type="submit" className="k-btn" disabled={!sure || busy}>
            {t('Record my observation', 'Записать наблюдение')}
          </button>
        </form>
      )}
    </li>
  );
}

export default function Revive() {
  const api = useApi();
  const cache = useQueryClient();
  const { t, device, setDevice } = usePreferences();
  const [profile, setProfile] = useState('network-certs');
  const [draft, setDraft] = useState({ model: '', rm: '', firmware: '' });
  const [manual, setManual] = useState({ model: '', rm: '', firmware: '' });
  const [scope, setScope] = useState('memory-card');
  const [patches, setPatches] = useState('');
  const [rightsSure, setRightsSure] = useState(false);
  const [variant, setVariant] = useState('');
  const [variantSure, setVariantSure] = useState(false);
  const call = <T,>(body: Record<string, unknown>, schema: import('zod').ZodType<T>) =>
    api.request('/api/revive', body as never, schema);
  const root = ['revive', device] as const;

  const state = useQuery({
    queryKey: ['revive', '', 'state'],
    queryFn: () => call({ action: 'state' }, stateSchema),
  });
  const inspect = useQuery({
    queryKey: [...root, 'inspect', manual],
    queryFn: () => call({ action: 'inspect', device, manual }, inspectSchema),
    staleTime: 0,
    retry: false,
  });
  const plan = useQuery({
    queryKey: [...root, 'plan', profile, manual],
    queryFn: () => call({ action: 'plan', device, profile, manual }, planSchema),
    staleTime: 0,
    retry: false,
  });
  const refresh = () => cache.invalidateQueries({ queryKey: ['revive'] });
  const act = useMutation({
    mutationFn: (body: Record<string, unknown>) => call({ device, manual, ...body }, simpleSchema),
    onSuccess: refresh,
  });
  const verify = useMutation({
    mutationFn: () => call({ action: 'verify', device, manual }, verifySchema),
  });

  // A single visible connection is selected for the user; several are never guessed between.
  const only = inspect.data?.devices.length === 1 ? inspect.data.devices[0] : undefined;
  useEffect(() => {
    if (!device && only) setDevice(only.id);
  }, [device, only, setDevice]);
  const profiles = Object.values(state.data?.profiles ?? {});
  const noConnection = inspect.data?.reason === 'no-connection';
  const selected = inspect.data?.facts['profile']?.value;
  const needsVariant = selected === 'nokia-n97-mini';

  return (
    <>
      <PageHeader
        title={t('SymPort Revive', 'SymPort Revive')}
        subtitle={t(
          'Inspect the phone, see a plan, prepare safely, verify the result. Nothing here installs software.',
          'Проверьте телефон, посмотрите план, безопасно подготовьтесь и проверьте результат. Здесь ничего не устанавливается.',
        )}
        actions={<DeviceSelect value={device} onChange={setDevice} />}
      />
      <p className="disclaimer">
        {t(
          'Copying a file to the phone is not installation. Anything you type is shown separately from what the device reported. No protection is bypassed and no system partition is written.',
          'Копирование файла на телефон — не установка. Всё, что вы вводите, показывается отдельно от ответа устройства. Защита не обходится, системные разделы не пишутся.',
        )}
      </p>
      {inspect.error && <ErrorMessage error={inspect.error} />}
      {noConnection ? (
        <EmptyState icon={PlugZap} title={t('No phone connection', 'Нет подключения к телефону')}>
          <ol>
            <li>
              {t(
                'Install and start the SymPort Windows Bridge, or enrol a drive.',
                'Установите и запустите SymPort Windows Bridge или добавьте диск.',
              )}
            </li>
            <li>
              {t(
                'Open “My phone → Connection” and follow the first-connection wizard.',
                'Откройте «Мой телефон → Подключение» и пройдите мастер первого подключения.',
              )}
            </li>
            <li>
              {t(
                'Return here: Revive reads the connection, it does not create one.',
                'Вернитесь сюда: Revive читает подключение, но не создаёт его.',
              )}
            </li>
          </ol>
        </EmptyState>
      ) : (
        inspect.data && (
          <div className="k-grid k-grid--wide-left">
            <SectionPanel
              title={t('What was observed', 'Что удалось определить')}
              meta={inspect.data.device ?? undefined}
            >
              {!inspect.data.device && (
                <p className="k-note-line">
                  {t(
                    'Select a connection to read its details.',
                    'Выберите подключение, чтобы прочитать данные.',
                  )}
                </p>
              )}
              <Facts facts={inspect.data.facts} />
              {inspect.data.conflict && (
                <p role="status" className="rv-conflict">
                  {t(
                    'What you typed contradicts the device report; the device report is used.',
                    'Введённое вами противоречит ответу устройства; используется ответ устройства.',
                  )}
                </p>
              )}
            </SectionPanel>
            <SectionPanel
              title={t('Typed by you (not a device report)', 'Введено вами (не отчёт устройства)')}
            >
              <form
                className="rv-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  setManual(draft);
                }}
              >
                {(['model', 'rm', 'firmware'] as const).map((field) => (
                  <label key={field}>
                    {
                      {
                        model: t('Model', 'Модель'),
                        rm: t('RM code', 'Код RM'),
                        firmware: t('Firmware', 'Прошивка'),
                      }[field]
                    }
                    <input
                      value={draft[field]}
                      maxLength={120}
                      onChange={(e) => setDraft({ ...draft, [field]: e.target.value })}
                    />
                  </label>
                ))}
                <button type="submit" className="k-btn">
                  {t('Use for the checks', 'Использовать в проверках')}
                </button>
              </form>
              <hr />
              <form
                className="rv-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  act.mutate({
                    action: 'observe',
                    kind: 'rights',
                    scope,
                    patches: patches
                      .split(',')
                      .map((p) => p.trim())
                      .filter(Boolean),
                    confirm: rightsSure,
                  });
                  setRightsSure(false);
                }}
              >
                <label>
                  {t('Installation rights you observed', 'Права установки, которые вы наблюдали')}
                  <select value={scope} onChange={(e) => setScope(e.target.value)}>
                    <option value="none">{t('None / unknown', 'Нет / неизвестно')}</option>
                    <option value="memory-card">
                      {t('Memory card only', 'Только карта памяти')}
                    </option>
                    <option value="device">{t('Device level', 'Уровень устройства')}</option>
                  </select>
                </label>
                <label>
                  {t(
                    'Patches seen in ROMPatcher+ (comma separated)',
                    'Патчи в ROMPatcher+ (через запятую)',
                  )}
                  <input value={patches} onChange={(e) => setPatches(e.target.value)} />
                </label>
                <label className="rv-check">
                  <input
                    type="checkbox"
                    checked={rightsSure}
                    onChange={(e) => setRightsSure(e.target.checked)}
                  />
                  {t('This is my own observation', 'Это моё собственное наблюдение')}
                </label>
                <button
                  type="submit"
                  className="k-btn"
                  disabled={!rightsSure || !inspect.data.device || act.isPending}
                >
                  {t('Record rights', 'Записать права')}
                </button>
              </form>
              {needsVariant && (
                <>
                  <hr />
                  <form
                    className="rv-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      act.mutate({
                        action: 'observe',
                        kind: 'variant',
                        confirmed: true,
                        label: variant,
                        confirm: variantSure,
                      });
                    }}
                  >
                    <label>
                      {t(
                        'Exact N97 mini variant (RM) you checked on the label',
                        'Точная модификация N97 mini (RM) с наклейки',
                      )}
                      <input
                        value={variant}
                        maxLength={60}
                        onChange={(e) => setVariant(e.target.value)}
                      />
                    </label>
                    <label className="rv-check">
                      <input
                        type="checkbox"
                        checked={variantSure}
                        onChange={(e) => setVariantSure(e.target.checked)}
                      />
                      {t('I confirm this variant', 'Подтверждаю эту модификацию')}
                    </label>
                    <button type="submit" className="k-btn" disabled={!variantSure || !variant}>
                      {t('Confirm variant', 'Подтвердить модификацию')}
                    </button>
                  </form>
                </>
              )}
              {act.error && <ErrorMessage error={act.error} />}
            </SectionPanel>
          </div>
        )
      )}

      <ReviveHome device={device} manual={manual} onOpen={setProfile} />

      <SectionPanel title={t('Preparation wizards', 'Мастера подготовки')}>
        <div
          className="rv-profiles"
          role="group"
          aria-label={t('Wizard profile', 'Профиль мастера')}
        >
          {profiles.map((p) => (
            <button
              key={p.id}
              type="button"
              className="rv-profile"
              aria-pressed={profile === p.id}
              onClick={() => setProfile(p.id)}
            >
              <strong>{t(p.title.en, p.title.ru)}</strong>
              <span>{t(p.summary.en, p.summary.ru)}</span>
            </button>
          ))}
        </div>
        {plan.error && <ErrorMessage error={plan.error} />}
        {plan.data && (
          <>
            <p className="rv-overall">
              {t('Overall', 'Итого')}: <StatusBadge status={plan.data.status} />
            </p>
            <Checks checks={plan.data.checks} />
            <h3>{t('Operations', 'Операции')}</h3>
            <ul className="rv-ops">
              {plan.data.operations.map((op) => (
                <OperationItem
                  key={op.id}
                  op={op}
                  busy={act.isPending}
                  onRecord={(operation, result, note) =>
                    act.mutate({ action: 'record', operation, result, note, confirm: true })
                  }
                />
              ))}
            </ul>
            <p className="k-note-line">{plan.data.statement}</p>
          </>
        )}
        {profile === 'post-check' && (
          <div className="rv-verify">
            <div className="k-toolbar">
              <button
                type="button"
                className="k-btn"
                disabled={!inspect.data?.device || act.isPending}
                onClick={() => act.mutate({ action: 'baseline' })}
              >
                <LifeBuoy size={14} aria-hidden="true" />{' '}
                {t('Save baseline now', 'Сохранить исходное состояние')}
              </button>
              <button
                type="button"
                className="k-btn k-btn--primary"
                disabled={!inspect.data?.device || verify.isPending}
                onClick={() => verify.mutate()}
              >
                {t('Re-read and compare', 'Перечитать и сравнить')}
              </button>
            </div>
            {inspect.data?.baseline && (
              <p className="k-note-line">
                {t('Baseline saved', 'Исходное состояние сохранено')}:{' '}
                {inspect.data.baseline.slice(0, 16)}
              </p>
            )}
            {verify.error && <ErrorMessage error={verify.error} />}
            {verify.data && (
              <div role="status" className="rv-diff">
                {verify.data.phone_changed && (
                  <p>
                    {t(
                      'The connection identity differs from the baseline (other phone, firmware or link).',
                      'Идентичность подключения отличается от исходной (другой телефон, прошивка или канал).',
                    )}
                  </p>
                )}
                {verify.data.diff.length === 0 ? (
                  <p>
                    {verify.data.baseline
                      ? t(
                          'No observable difference from the baseline.',
                          'Наблюдаемых отличий от исходного состояния нет.',
                        )
                      : t('No baseline to compare with.', 'Нет исходного состояния для сравнения.')}
                  </p>
                ) : (
                  <ul className="k-list">
                    {verify.data.diff.map((d) => (
                      <li key={d.field}>
                        <span>{d.field}</span>
                        <span>
                          {String(d.before ?? '—')} → {String(d.after ?? '—')}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="k-note-line">{verify.data.statement}</p>
              </div>
            )}
          </div>
        )}
      </SectionPanel>
      {profile === 'network-certs' && <ReviveTls device={device} manual={manual} />}
      {profile === 'reborn-n95' && <ReviveReborn device={device} manual={manual} />}
      {profile === 'legacy-services' && <ReviveServices device={device} manual={manual} />}
      {profile === 'post-check' && <ReviveAgent />}
    </>
  );
}
