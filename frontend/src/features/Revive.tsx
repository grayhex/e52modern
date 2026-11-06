import { useEffect, useId, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Boxes,
  ClipboardCheck,
  Cloud,
  Globe,
  LifeBuoy,
  PackagePlus,
  PlugZap,
  Smartphone,
  Usb,
  type LucideIcon,
} from 'lucide-react';
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
import ReviveAddons from './ReviveAddons';
import ReviveHome from './ReviveHome';
import ReviveReborn from './ReviveReborn';
import ReviveServices from './ReviveServices';
import ReviveTls from './ReviveTls';
import { isDeveloperRoute } from '../nav/routes';
import { goRevive } from './reviveNav';
import { st } from './statements';
import {
  inspectSchema,
  planSchema,
  simpleSchema,
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
  const { t, language } = usePreferences();
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
              {fact.note && <small>{st(language, fact.note)}</small>}
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

export type ReviveSection =
  'home' | 'network' | 'kit' | 'services' | 'reborn' | 'addons' | 'post-check';
const SECTION_PROFILE: Record<Exclude<ReviveSection, 'home'>, string> = {
  network: 'network-certs',
  kit: 'app-kit',
  services: 'legacy-services',
  reborn: 'reborn-n95',
  addons: 'addons',
  'post-check': 'post-check',
};
const SECTION_TITLE: Record<ReviveSection, [string, string, string, string]> = {
  home: [
    'Recovery centre',
    'Центр восстановления',
    'Inspect the phone, see what can be improved and prepare it step by step. Nothing here installs software.',
    'Проверьте телефон, посмотрите, что можно улучшить, и подготовьте его по шагам. Здесь ничего не устанавливается.',
  ],
  network: [
    'Network & TLS',
    'Сеть и TLS',
    'Modern TLS components, trusted certificates and a connection check for old Symbian applications.',
    'Современные TLS-компоненты, доверенные сертификаты и проверка соединения для старых приложений Symbian.',
  ],
  kit: [
    'Application kit',
    'Набор приложений',
    'Check space and transport, copy a verified kit to the phone and install it there.',
    'Проверка места и транспорта, копирование проверенного набора и установка на телефоне.',
  ],
  services: [
    'Online services',
    'Онлайн-сервисы',
    'Old system endpoints, their working replacements and what has been confirmed.',
    'Старые системные адреса, их рабочие замены и что подтверждено.',
  ],
  reborn: [
    'Reborn for N95',
    'Reborn для N95',
    'Step-by-step preparation for the Reborn Hybrid CFW alpha on the Nokia N95.',
    'Пошаговая подготовка к Reborn Hybrid CFW alpha на Nokia N95.',
  ],
  addons: [
    'Add-ons & patches',
    'Дополнения и патчи',
    'Optional add-ons checked against your model, and the Patch Manager inventory.',
    'Необязательные дополнения, проверенные под вашу модель, и инвентарь Patch Manager.',
  ],
  'post-check': [
    'After installation',
    'После установки',
    'Compare the phone with its saved state and record what you saw on the screen.',
    'Сравните телефон с сохранённым состоянием и запишите, что вы увидели на экране.',
  ],
};
const SECTION_ICON: Record<Exclude<ReviveSection, 'home'>, LucideIcon> = {
  network: Globe,
  kit: Boxes,
  services: Cloud,
  reborn: Usb,
  addons: PackagePlus,
  'post-check': ClipboardCheck,
};

type Manual = { model: string; rm: string; firmware: string };
const EMPTY_MANUAL: Manual = { model: '', rm: '', firmware: '' };
/** What the user typed survives moving between Revive pages, never the page reload. */
function useManual() {
  const [manual, setManualState] = useState<Manual>(() => {
    try {
      return {
        ...EMPTY_MANUAL,
        ...JSON.parse(sessionStorage.getItem('symport-revive-manual') ?? '{}'),
      };
    } catch {
      return EMPTY_MANUAL;
    }
  });
  const setManual = (value: Manual) => {
    setManualState(value);
    try {
      sessionStorage.setItem('symport-revive-manual', JSON.stringify(value));
    } catch {
      /* storage is optional */
    }
  };
  return [manual, setManual] as const;
}

export default function Revive({ section = 'home' }: { section?: ReviveSection }) {
  const api = useApi();
  const cache = useQueryClient();
  const { t, device, setDevice, mode } = usePreferences();
  const profile = section === 'home' ? 'network-certs' : SECTION_PROFILE[section];
  const [manual, setManual] = useManual();
  const [draft, setDraft] = useState(manual);
  const [scope, setScope] = useState('memory-card');
  const [patches, setPatches] = useState('');
  const [rightsSure, setRightsSure] = useState(false);
  const [variant, setVariant] = useState('');
  const [variantSure, setVariantSure] = useState(false);
  const call = <T,>(body: Record<string, unknown>, schema: import('zod').ZodType<T>) =>
    api.request('/api/revive', body as never, schema);
  const root = ['revive', device] as const;

  const inspect = useQuery({
    queryKey: [...root, 'inspect', manual],
    queryFn: () => call({ action: 'inspect', device, manual }, inspectSchema),
    staleTime: 0,
    retry: false,
  });
  const plan = useQuery({
    queryKey: [...root, 'plan', profile, manual],
    queryFn: () => call({ action: 'plan', device, profile, manual }, planSchema),
    enabled: section !== 'home',
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
  const noConnection = inspect.data?.reason === 'no-connection';
  const selected = inspect.data?.facts['profile']?.value;
  const needsVariant = selected === 'nokia-n97-mini';
  const [titleEn, titleRu, subEn, subRu] = SECTION_TITLE[section];
  const facts = inspect.data?.facts ?? {};

  return (
    <>
      <PageHeader
        title={t(titleEn, titleRu)}
        subtitle={t(subEn, subRu)}
        actions={<DeviceSelect value={device} onChange={setDevice} />}
      />
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
        inspect.data &&
        section !== 'home' && (
          <p className="rv-strip" data-testid="revive-strip">
            <Smartphone size={15} aria-hidden="true" />
            {(['model', 'rm', 'firmware'] as const).map((id) => (
              <span key={id} className="rv-strip-item">
                <small>
                  {
                    { model: t('Model', 'Модель'), rm: 'RM', firmware: t('Firmware', 'Прошивка') }[
                      id
                    ]
                  }
                </small>
                {facts[id] ? formatFact(id, facts[id], t) : t('not reported', 'не сообщено')}
              </span>
            ))}
            <a className="k-link" href="#revive/home">
              {t('Details', 'Подробнее')}
            </a>
          </p>
        )
      )}

      {section === 'home' && !noConnection && inspect.data && (
        <>
          <SectionPanel title={t('Preparation wizards', 'Мастера подготовки')}>
            <div className="rv-profiles" role="group" aria-label={t('Wizards', 'Мастера')}>
              {(Object.keys(SECTION_PROFILE) as Exclude<ReviveSection, 'home'>[])
                .filter((id) => mode === 'developer' || !isDeveloperRoute(`revive/${id}`))
                .map((id) => {
                  const Icon = SECTION_ICON[id];
                  const [en, ru, descEn, descRu] = SECTION_TITLE[id];
                  return (
                    <a key={id} className="rv-profile" href={`#revive/${id}`} data-wizard={id}>
                      <strong>
                        <Icon size={16} aria-hidden="true" /> {t(en, ru)}
                      </strong>
                      <span>{t(descEn, descRu)}</span>
                    </a>
                  );
                })}
            </div>
          </SectionPanel>
          <ReviveHome device={device} manual={manual} onOpen={goRevive} />
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
              <details className="rv-more">
                <summary>{t('Installation rights and patches', 'Права установки и патчи')}</summary>
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
              </details>
              {needsVariant && (
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
              )}
              {act.error && <ErrorMessage error={act.error} />}
            </SectionPanel>
          </div>
          <p className="disclaimer">
            {t(
              'Copying a file to the phone is not installation: finish it on the phone screen. What you type is always shown separately from the device report.',
              'Копирование файла на телефон — не установка: завершите её на экране телефона. Введённое вами всегда показывается отдельно от ответа устройства.',
            )}
          </p>
        </>
      )}

      {section !== 'home' && !noConnection && (
        <>
          {plan.error && <ErrorMessage error={plan.error} />}
          {plan.data && (
            <SectionPanel
              title={t('Readiness', 'Готовность')}
              meta={<StatusBadge status={plan.data.status} />}
            >
              <details className="rv-more" open>
                <summary>{t('Checks and operations', 'Проверки и операции')}</summary>
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
              </details>
            </SectionPanel>
          )}
          {section === 'post-check' && (
            <SectionPanel
              title={t('Compare with the saved state', 'Сравнение с сохранённым состоянием')}
            >
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
                          : t(
                              'No baseline to compare with.',
                              'Нет исходного состояния для сравнения.',
                            )}
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
                  </div>
                )}
              </div>
            </SectionPanel>
          )}
          {section === 'network' && <ReviveTls device={device} manual={manual} />}
          {section === 'reborn' && <ReviveReborn device={device} manual={manual} />}
          {section === 'services' && <ReviveServices device={device} manual={manual} />}
          {section === 'post-check' && <ReviveAgent />}
          {section === 'addons' && <ReviveAddons device={device} manual={manual} />}
        </>
      )}
    </>
  );
}
