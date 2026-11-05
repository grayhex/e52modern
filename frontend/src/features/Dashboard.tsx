import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTheme } from '@mui/material/styles';
import { BarChart } from '@mui/x-charts/BarChart';
import { LineChart } from '@mui/x-charts/LineChart';
import { PieChart } from '@mui/x-charts/PieChart';
import {
  Activity as ActivityIcon,
  AppWindow,
  Battery,
  Clock3,
  DatabaseBackup,
  FolderOpen,
  HardDrive,
  History,
  PackageSearch,
  PlugZap,
  RefreshCw,
  Signal,
  Users,
} from 'lucide-react';
import { useDevices, useModels, keys } from '../api/queries';
import { useApi, usePreferences } from '../state/app';
import { useWorkspace } from '../hooks/useWorkspace';
import { ChartTheme } from '../dashboard/ChartTheme';
import { formatBytes, localeFor, perDay, storage, timeLabel } from '../dashboard/derive';
import { useLinkedVolume } from '../dashboard/linkedVolume';
import { SERVICES, opState } from '../api/capabilities';
import { measurementsSchema } from '../api/p1';
import type { Device, PhoneModel } from '../api/contracts';
import {
  ActionToolbar,
  DeviceIdentity,
  EmptyState,
  ErrorState,
  GenericPhone,
  Metric,
  PageHeader,
  SectionPanel,
  Skeleton,
  StatusIndicator,
  type Tone,
} from '../components/kit';

const base = import.meta.env.BASE_URL;
const asset = (path: string) => `${base}${path.replace(/^\//, '')}`;
const operationLabel = new Map(
  SERVICES.flatMap((s) => s.ops.map(([op, en, ru]) => [op, [en, ru]] as const)),
);

/** Landing page: only values the selected transport really reports; everything else is listed as not reported. */
export default function Dashboard() {
  return (
    <ChartTheme>
      <Overview />
    </ChartTheme>
  );
}

function Overview() {
  const palette = useTheme().palette;
  const api = useApi();
  const { device, language, t } = usePreferences();
  const locale = localeFor(language);
  const devices = useDevices();
  const models = useModels();
  const workspace = useWorkspace();
  const list = devices.data?.devices ?? [];
  const selected: Device | undefined =
    list.find((d) => d.id === device) ??
    list.find((d) => d.connected && d.model) ??
    list.find((d) => d.connected) ??
    list[0];
  const connected = Boolean(selected?.connected);
  const journal = useQuery({
    queryKey: keys.history,
    queryFn: ({ signal }) => api.history(signal),
    refetchInterval: 30000,
  });
  const operations = journal.data?.operations ?? [];
  // Counters belong to the connection that reported them; a linked volume is the user's explicit choice.
  const linked = useLinkedVolume(selected, list);
  const space = storage(linked.volume);
  const samples = useQuery({
    queryKey: ['diagnostics', selected?.id],
    queryFn: ({ signal }) =>
      api.request(
        '/api/diagnostics',
        { action: 'history', device: selected?.id ?? '' },
        measurementsSchema,
        signal,
      ),
    enabled: connected && Boolean(selected?.id),
    retry: false,
  });
  const backups = (workspace.data?.backups ?? []).filter((b) => typeof b.created === 'string');
  const lastBackup = backups
    .map((b) => String(b.created))
    .sort()
    .at(-1);
  const matrix = selected?.capability_matrix;
  const verified = matrix ? Object.entries(matrix).filter(([, s]) => s.status === 'available') : [];
  const updated = devices.dataUpdatedAt
    ? new Date(devices.dataUpdatedAt).toLocaleTimeString(locale, {
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  const header = (
    <PageHeader
      title={t('Device overview', 'Обзор устройства')}
      actions={
        <>
          {updated && (
            <span className="k-meta">
              {t('Checked', 'Проверено')}: {updated}
            </span>
          )}
          <button
            type="button"
            className="k-btn"
            disabled={devices.isFetching}
            onClick={() => {
              void devices.refetch();
            }}
          >
            <RefreshCw size={14} aria-hidden="true" />
            {t('Refresh', 'Обновить')}
          </button>
        </>
      }
    />
  );

  if (devices.isPending)
    return (
      <div className="k-stack mui-dashboard">
        {header}
        <SectionPanel>
          <Skeleton lines={5} />
        </SectionPanel>
      </div>
    );
  if (devices.isError && !devices.data)
    return (
      <div className="k-stack mui-dashboard">
        {header}
        <ErrorState title={t('Devices could not be read', 'Не удалось получить список устройств')}>
          {devices.error.message}
        </ErrorState>
      </div>
    );
  if (!connected)
    return (
      <div className="k-stack mui-dashboard">
        {header}
        <NoPhone
          models={models}
          selected={selected}
          onRetry={() => void devices.refetch()}
          busy={devices.isFetching}
        />
      </div>
    );

  const profile = selected?.model_profile;
  type MetricRow = {
    key: string;
    icon: typeof Battery;
    label: string;
    value: string;
    progress?: number;
    note?: string;
  };
  const metrics = [
    selected?.battery != null && {
      key: 'battery',
      icon: Battery,
      label: t('Battery', 'Заряд батареи'),
      value: `${selected.battery}%`,
      progress: selected.battery,
    },
    selected?.signal != null && {
      key: 'signal',
      icon: Signal,
      label: t('Signal', 'Уровень сигнала'),
      value: `${selected.signal}%`,
      progress: selected.signal,
    },
    space && {
      key: 'free',
      icon: HardDrive,
      label: t('Free space', 'Свободно на накопителе'),
      value: formatBytes(space.free),
      progress: 100 - space.usedPercent,
      note: `${t('of', 'из')} ${formatBytes(space.total)}`,
    },
    selected?.life_timer_hours != null && {
      key: 'life',
      icon: Clock3,
      label: t('Life timer', 'Счётчик часов'),
      value: `${selected.life_timer_hours.toFixed(1)} ${t('h', 'ч')}`,
    },
    matrix && {
      key: 'verified',
      icon: ActivityIcon,
      label: t('Verified operations', 'Подтверждено операций'),
      value: `${verified.length} / ${Object.keys(matrix).length}`,
      note: t('by read-only probes', 'безопасными проверками'),
    },
    lastBackup && {
      key: 'backup',
      icon: DatabaseBackup,
      label: t('Last server backup', 'Последняя копия'),
      value: new Date(lastBackup).toLocaleDateString(locale),
      note: `${backups.length} ${t('stored on the server', 'хранится на сервере')}`,
    },
  ].filter((m): m is MetricRow => m !== null && typeof m === 'object');
  const missing = [
    selected?.battery == null && t('battery', 'батарея'),
    selected?.signal == null && t('signal', 'сигнал'),
    !space && t('storage counters', 'счётчики накопителя'),
    selected?.life_timer_hours == null && t('life timer', 'счётчик часов'),
  ].filter(Boolean);

  const sampleRows = (samples.data?.measurements ?? []).filter(
    (m) => m.battery != null || m.signal != null,
  );
  const showHistory = sampleRows.length >= 3;

  return (
    <div className="k-stack mui-dashboard">
      {header}
      <SectionPanel className="k-hero">
        <DeviceIdentity
          name={
            (profile ? t(profile.name, profile.name_ru ?? profile.name) : undefined) ??
            selected?.model ??
            selected?.name ??
            t('Symbian phone', 'Телефон Symbian')
          }
          subtitle={
            profile
              ? [
                  profile.symbian && `Symbian ${profile.symbian}`,
                  `S60 ${profile.s60}`,
                  profile.screen &&
                    `${profile.screen.width}×${profile.screen.height} (${profile.screen.orientation === 'landscape' ? t('landscape', 'альбомная') : t('portrait', 'книжная')})`,
                ]
                  .filter(Boolean)
                  .join(' · ')
              : t(
                  'The connection did not report a phone model.',
                  'Подключение не сообщило модель телефона.',
                )
          }
          status={
            <>
              <StatusIndicator tone="ok">{t('Connected', 'Подключено')}</StatusIndicator>
              {selected?.evidence && <span className="k-meta">{selected.evidence}</span>}
            </>
          }
          facts={[
            {
              label: t('Firmware', 'Прошивка'),
              value: selected?.firmware || t('No data', 'Нет данных'),
              note: selected?.rm ? `RM ${selected.rm}` : null,
            },
            ...(space
              ? [
                  {
                    label: t('Storage', 'Накопитель'),
                    value: formatBytes(space.total),
                    note: `${t('free', 'свободно')} ${formatBytes(space.free)}`,
                  },
                ]
              : []),
            {
              label: t('Transport', 'Транспорт'),
              value: selected?.transport ?? '—',
              note: selected?.usb_mode ? `USB: ${selected.usb_mode}` : null,
            },
          ]}
          {...artwork(profile, models, t)}
          actions={<HeroActions device={selected} volume={linked.volume} />}
        />
      </SectionPanel>

      {metrics.length > 0 && (
        <div className="k-metrics">
          {metrics.map(({ key, ...m }) => (
            <Metric key={key} {...m} />
          ))}
        </div>
      )}
      {missing.length > 0 && (
        <p className="k-note-line">
          {t('Not reported by this transport', 'Не сообщается этим транспортом')}:{' '}
          {missing.join(', ')}.
        </p>
      )}

      <div className={`k-grid ${showHistory ? 'k-grid--3' : 'k-grid--2'}`}>
        <SectionPanel
          title={t('Storage', 'Хранилище')}
          meta={space ? `${t('Total', 'Всего')}: ${formatBytes(space.total)}` : undefined}
        >
          <StoragePanel
            space={space}
            linked={linked}
            usedColor={palette.primary.main}
            freeColor="#a7bedd"
            emptyColor="#e2e7ed"
          />
        </SectionPanel>
        <SectionPanel
          title={t('SymPort operations, 7 days', 'Операции SymPort за 7 дней')}
          meta={`${operations.length} ${t('in the log', 'в журнале')}`}
        >
          <DayChart operations={operations} color={palette.primary.main} />
          {!operations.length && (
            <p className="k-note-line">
              {t('No operations recorded yet.', 'Операций пока не записано.')}
            </p>
          )}
        </SectionPanel>
        {showHistory && (
          <SectionPanel
            title={t('Battery and signal', 'Батарея и сигнал')}
            meta={`${sampleRows.length} ${t('measurements', 'измерений')}`}
          >
            <HistoryChart rows={sampleRows} locale={locale} />
          </SectionPanel>
        )}
      </div>

      <div className="k-grid k-grid--2">
        <SectionPanel title={t('Device state', 'Состояние устройства')}>
          <StateList device={selected} hasBackup={Boolean(lastBackup)} />
        </SectionPanel>
        <SectionPanel
          title={t('Device log', 'Журнал устройства')}
          actions={
            <a className="k-link" href="#tools/activity">
              {t('Show all', 'Показать все')}
            </a>
          }
        >
          {operations.length ? (
            <ul className="k-list">
              {operations
                .slice(-5)
                .reverse()
                .map((op, i) => (
                  <li key={`${op.time}-${i}`}>
                    <span className="k-log">
                      <History size={16} aria-hidden="true" />
                      <strong>{op.action}</strong>
                      <StatusIndicator tone={op.status === 'success' ? 'ok' : 'warn'}>
                        {op.status}
                      </StatusIndicator>
                    </span>
                    <span className="k-meta">{timeLabel(op.time, locale)}</span>
                  </li>
                ))}
            </ul>
          ) : (
            <p className="k-note-line">{t('Nothing recorded yet.', 'Пока ничего не записано.')}</p>
          )}
        </SectionPanel>
      </div>

      {verified.length > 0 && (
        <p className="k-note-line">
          {t(
            'Verified by a read-only probe (details: Connection):',
            'Подтверждено безопасной проверкой чтения (подробнее: «Подключение»):',
          )}{' '}
          {verified
            .map(([op]) => {
              const label = operationLabel.get(op);
              return label ? t(label[0], label[1]) : op;
            })
            .join(' · ')}
        </p>
      )}
    </div>
  );
}

/** Product picture: registry artwork, else a labelled generic outline; never a made-up photo. */
function artwork(
  profile: Device['model_profile'],
  models: PhoneModel[],
  t: (en: string, ru: string) => string,
): { image: React.ReactNode; illustration: boolean; caption?: React.ReactNode } {
  if (profile?.image)
    return {
      image: <img src={asset(profile.image)} alt={profile.name} />,
      illustration: false,
    };
  if (profile)
    return {
      image: (
        <GenericPhone label={t('Generic phone illustration', 'Обобщённая иллюстрация телефона')} />
      ),
      illustration: true,
      caption: t(
        'Generic illustration: no artwork for this model yet',
        'Обобщённая иллюстрация: для этой модели пока нет изображения',
      ),
    };
  return { image: <Chooser models={models} t={t} />, illustration: true };
}

/** Unidentified model: choose among *registered* phones' artwork, clearly an illustration. */
function Chooser({ models, t }: { models: PhoneModel[]; t: (en: string, ru: string) => string }) {
  const withImage = models.filter((m) => m.image);
  const [chosen, setChosen] = useState('');
  const current = withImage.find((m) => m.id === chosen) ?? withImage[0];
  return (
    <div className="k-chooser">
      {current?.image ? (
        <img
          src={asset(current.image)}
          alt={t('Illustration (model not identified)', 'Иллюстрация (модель не определена)')}
        />
      ) : (
        <GenericPhone label={t('Generic phone illustration', 'Обобщённая иллюстрация телефона')} />
      )}
      <span className="k-meta">
        {t(
          'Illustration only — the connection did not report a model',
          'Только иллюстрация — подключение не сообщило модель',
        )}
      </span>
      {withImage.length > 1 && (
        <div
          className="k-toolbar"
          role="group"
          aria-label={t('Illustration model', 'Модель иллюстрации')}
        >
          {withImage.map((m) => (
            <button
              key={m.id}
              type="button"
              className={`k-btn k-btn--small ${current?.id === m.id ? 'k-btn--primary' : ''}`}
              aria-pressed={current?.id === m.id}
              onClick={() => setChosen(m.id)}
            >
              {m.model}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function allowed(device: Device | undefined, ...ops: string[]) {
  if (!device?.capability_matrix) return true; // a component without probes: the page itself explains limits
  return ops.some((op) => {
    const s = opState(device, op);
    return s !== undefined && s.attempt !== 'blocked';
  });
}

/** Only actions this connection can really attempt; the rest are named once, not shown as dead buttons. */
function HeroActions({
  device,
  volume,
}: {
  device: Device | undefined;
  volume: Device | undefined;
}) {
  const { t } = usePreferences();
  const actions = [
    {
      icon: FolderOpen,
      label: t('Files', 'Файлы'),
      href: '#phone/files',
      ops: ['files.list'],
      primary: true,
    },
    {
      icon: Users,
      label: t('Contacts', 'Контакты'),
      href: '#phone/contacts',
      ops: ['contacts.read', 'contacts.stage'],
    },
    {
      icon: DatabaseBackup,
      label: t('Backup', 'Резервная копия'),
      href: '#phone/backups',
      ops: ['files.list'],
    },
    {
      icon: AppWindow,
      label: t('Install app', 'Установить приложение'),
      href: '#apps/catalog',
      ops: ['packages.transfer', 'packages.opp-push'],
    },
    {
      icon: PackageSearch,
      label: t('Check package', 'Проверить пакет'),
      href: '#apps/packages',
      ops: [],
    },
  ];
  // A linked memory-card volume serves the file actions; the phone itself serves personal data.
  const usable = actions.filter(
    (a) =>
      a.ops.length === 0 ||
      allowed(device, ...a.ops) ||
      (volume !== device && allowed(volume, ...a.ops)),
  );
  const hidden = actions.filter((a) => !usable.includes(a));
  return (
    <>
      <ActionToolbar label={t('Actions', 'Действия')}>
        {usable.map(({ icon: Icon, label, href, primary }) => (
          <a key={href} className={`k-btn ${primary ? 'k-btn--primary' : ''}`} href={href}>
            <Icon size={16} aria-hidden="true" />
            {label}
          </a>
        ))}
      </ActionToolbar>
      {hidden.length > 0 && (
        <p className="k-note-line">
          {t('Not available on this connection', 'Недоступно на этом подключении')}:{' '}
          {hidden.map((a) => a.label).join(', ')}.{' '}
          <a href="#phone/connection">{t('Why?', 'Почему?')}</a>
        </p>
      )}
    </>
  );
}

function NoPhone({
  models,
  selected,
  onRetry,
  busy,
}: {
  models: PhoneModel[];
  selected: Device | undefined;
  onRetry: () => void;
  busy: boolean;
}) {
  const { t } = usePreferences();
  const first = models.find((m) => m.image);
  return (
    <EmptyState
      title={t('No phone connected', 'Телефон не подключён')}
      media={
        first?.image ? (
          <img
            className="k-empty-art"
            src={asset(first.image)}
            alt={t('Illustration', 'Иллюстрация')}
          />
        ) : (
          <PlugZap size={40} aria-hidden="true" className="k-empty-icon" />
        )
      }
      actions={
        <>
          <a className="k-btn k-btn--primary" href="#phone/connection">
            {t('Open the connection wizard', 'Открыть мастер подключения')}
          </a>
          <button type="button" className="k-btn" disabled={busy} onClick={onRetry}>
            <RefreshCw size={14} aria-hidden="true" />
            {t('Find phone', 'Найти телефон')}
          </button>
        </>
      }
    >
      <ol>
        <li>
          {t(
            'Connect the phone with a data cable and choose PC Suite.',
            'Подключите телефон кабелем передачи данных и выберите PC Suite.',
          )}
        </li>
        <li>
          {t(
            'Start Windows Bridge on that PC, or use a local transport.',
            'Запустите Windows Bridge на этом ПК или используйте локальный транспорт.',
          )}
        </li>
        <li>
          {t(
            'Follow the wizard: it shows what is really answering at each step.',
            'Пройдите мастер: он показывает, что реально отвечает на каждом шаге.',
          )}
        </li>
      </ol>
      {selected && !selected.connected && (
        <p className="k-note-line">
          {selected.name ?? selected.id}: {selected.evidence ?? t('does not answer', 'не отвечает')}
        </p>
      )}
    </EmptyState>
  );
}

function StoragePanel({
  space,
  linked,
  usedColor,
  freeColor,
  emptyColor,
}: {
  space: ReturnType<typeof storage>;
  linked: ReturnType<typeof useLinkedVolume>;
  usedColor: string;
  freeColor: string;
  emptyColor: string;
}) {
  const { t } = usePreferences();
  return (
    <div className="k-storage">
      <PieChart
        width={180}
        height={180}
        hideLegend
        margin={{ top: 4, bottom: 4, left: 4, right: 4 }}
        series={[
          {
            innerRadius: 58,
            outerRadius: 86,
            paddingAngle: space ? 2 : 0,
            cornerRadius: 3,
            data: space
              ? [
                  { id: 'used', value: space.used, label: t('Used', 'Занято'), color: usedColor },
                  { id: 'free', value: space.free, label: t('Free', 'Свободно'), color: freeColor },
                ]
              : [{ id: 'none', value: 1, label: t('No data', 'Нет данных'), color: emptyColor }],
            valueFormatter: (item) => (space ? formatBytes(item.value) : '—'),
          },
        ]}
      />
      <div className="k-storage-legend">
        <p className="k-legend">
          <span className="k-swatch k-swatch--used" aria-hidden="true" />
          <strong>{t('Used', 'Занято')}</strong>{' '}
          {space ? `${formatBytes(space.used)} (${space.usedPercent}%)` : '—'}
        </p>
        <p className="k-legend">
          <span className="k-swatch k-swatch--free" aria-hidden="true" />
          <strong>{t('Free', 'Свободно')}</strong>{' '}
          {space ? `${formatBytes(space.free)} (${100 - space.usedPercent}%)` : '—'}
        </p>
        <p className="k-note-line">
          {space
            ? `${linked.volume?.name ?? linked.volume?.id ?? ''} · ` +
              (linked.isLinked
                ? t(
                    'Volume linked by you to this phone; it says nothing about phone memory or other cards.',
                    'Том, который вы связали с этим телефоном; о памяти телефона и других картах он ничего не говорит.',
                  )
                : t(
                    'Counters reported by this connection.',
                    'Счётчики, сообщённые этим подключением.',
                  ))
            : t(
                'This connection reports no storage counters.',
                'Это подключение не сообщает счётчики накопителя.',
              )}
        </p>
        {linked.candidates.length > 0 && (
          <label className="k-field">
            <span className="k-meta">
              {t('Link a memory card volume', 'Связать с томом карты памяти')}
            </span>
            <select
              value={linked.isLinked ? (linked.volume?.id ?? '') : ''}
              onChange={(event) => linked.link(event.target.value || null)}
            >
              <option value="">{t('Not linked', 'Не связан')}</option>
              {linked.candidates.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name ?? d.id}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    </div>
  );
}

function StateList({ device, hasBackup }: { device: Device | undefined; hasBackup: boolean }) {
  const { t } = usePreferences();
  const files = opState(device, 'files.list');
  const firmware = device?.firmware_update?.status;
  const rows: [string, Tone, string][] = [
    [t('Connection', 'Подключение'), 'ok', t('Connected', 'Подключено')],
    [
      t('File access', 'Доступ к файлам'),
      files?.status === 'available' ? 'ok' : files?.status === 'unsupported' ? 'off' : 'unknown',
      files?.status === 'available'
        ? t('Verified', 'Проверено')
        : files?.status === 'unsupported'
          ? t('Not supported here', 'Не поддерживается')
          : t('Not verified', 'Не проверено'),
    ],
    [
      t('Firmware vs reference', 'Прошивка и справочник'),
      firmware === 'older' ? 'warn' : firmware === 'current-in-reference' ? 'ok' : 'unknown',
      firmware === 'older'
        ? `${t('newer exists', 'есть новее')}: ${device?.firmware_update?.latest_known ?? '—'}`
        : firmware === 'current-in-reference'
          ? t('matches the reference', 'по справочнику')
          : t('No data', 'Нет данных'),
    ],
    [
      t('USB mode', 'USB-режим'),
      device?.usb_mode ? 'ok' : 'unknown',
      device?.usb_mode ?? t('Not reported', 'Не сообщается'),
    ],
    [
      t('Full backup', 'Полная копия'),
      hasBackup ? 'ok' : 'warn',
      hasBackup ? t('Exists on the server', 'Есть на сервере') : t('None yet', 'Ещё нет'),
    ],
  ];
  return (
    <ul className="k-list">
      {rows.map(([label, tone, text]) => (
        <li key={label}>
          <strong>{label}</strong>
          <StatusIndicator tone={tone}>{text}</StatusIndicator>
        </li>
      ))}
    </ul>
  );
}

function DayChart({
  operations,
  color,
}: {
  operations: { time: string; action: string; status: string }[];
  color: string;
}) {
  const { t } = usePreferences();
  const days = perDay(operations);
  return (
    <BarChart
      height={200}
      xAxis={[
        {
          scaleType: 'band',
          data: days.map((d) => d.label),
          label: t('Day of month', 'День месяца'),
        },
      ]}
      yAxis={[
        {
          tickMinStep: 1,
          min: 0,
          max: Math.max(1, ...days.map((d) => d.ok + d.other)),
          valueFormatter: (v: number) => String(Math.round(v)),
        },
      ]}
      series={[
        { data: days.map((d) => d.ok), label: t('Succeeded', 'Успешно'), stack: 'ops', color },
        {
          data: days.map((d) => d.other),
          label: t('Other outcome', 'Иной итог'),
          stack: 'ops',
          color: '#c28a2e',
        },
      ]}
      margin={{ left: 36, right: 8, top: 24, bottom: 36 }}
    />
  );
}

/** Real diagnostic samples only; a missing reading is a gap, never a zero. */
function HistoryChart({
  rows,
  locale,
}: {
  rows: { time: string; battery?: number | null | undefined; signal?: number | null | undefined }[];
  locale: string;
}) {
  const { t } = usePreferences();
  const points = rows.slice(-24);
  return (
    <LineChart
      height={200}
      xAxis={[
        {
          scaleType: 'point',
          data: points.map((p) =>
            new Date(p.time).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }),
          ),
        },
      ]}
      yAxis={[{ min: 0, max: 100 }]}
      series={[
        {
          data: points.map((p) => p.battery ?? null),
          label: t('Battery, %', 'Батарея, %'),
          connectNulls: false,
          color: '#124191',
        },
        {
          data: points.map((p) => p.signal ?? null),
          label: t('Signal, %', 'Сигнал, %'),
          connectNulls: false,
          color: '#c28a2e',
        },
      ]}
      margin={{ left: 36, right: 8, top: 24, bottom: 28 }}
    />
  );
}
