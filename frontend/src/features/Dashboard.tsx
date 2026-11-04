import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import createCache from '@emotion/cache';
import { CacheProvider } from '@emotion/react';
import { ThemeProvider, useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ButtonBase from '@mui/material/ButtonBase';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { BarChart } from '@mui/x-charts/BarChart';
import { PieChart } from '@mui/x-charts/PieChart';
import {
  Activity as ActivityIcon,
  AppWindow,
  Battery,
  Clock3,
  Cpu,
  DatabaseBackup,
  FolderOpen,
  HardDrive,
  History,
  PackageSearch,
  RefreshCw,
  Signal,
  Usb,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { useDevices, keys } from '../api/queries';
import { useApi, usePreferences } from '../state/app';
import { useWorkspace } from '../hooks/useWorkspace';
import { nokiaTheme } from '../dashboard/muiTheme';
import { formatBytes, localeFor, perDay, storage, timeLabel } from '../dashboard/derive';
import { useLinkedVolume } from '../dashboard/linkedVolume';
import type { Device } from '../api/contracts';

const base = import.meta.env.BASE_URL;

/** Landing page: only values the selected transport really reports; anything else says "no data". */
export default function Dashboard() {
  const { theme } = usePreferences();
  const api = useApi();
  const dark =
    theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  const cache = useMemo(
    () => createCache({ key: 'mui', nonce: api.styleNonce, prepend: true }),
    [api.styleNonce],
  );
  const muiTheme = useMemo(() => nokiaTheme(dark ? 'dark' : 'light'), [dark]);
  return (
    <CacheProvider value={cache}>
      <ThemeProvider theme={muiTheme}>
        <Overview />
      </ThemeProvider>
    </CacheProvider>
  );
}

function Overview() {
  const palette = useTheme().palette;
  const usedColor = palette.primary.main;
  const emptyColor = palette.mode === 'dark' ? '#3a4c60' : '#e2e7ed';
  const freeColor = palette.mode === 'dark' ? '#547bb1' : '#a7bedd';
  const api = useApi();
  const { device, language, t } = usePreferences();
  const locale = localeFor(language);
  const devices = useDevices();
  const workspace = useWorkspace();
  const selected: Device | undefined =
    devices.data?.devices.find((d) => d.id === device) ??
    devices.data?.devices.find((d) => d.connected && d.model) ??
    devices.data?.devices.find((d) => d.connected) ??
    devices.data?.devices[0];
  const journal = useQuery({
    queryKey: keys.history,
    queryFn: ({ signal }) => api.history(signal),
    refetchInterval: 30000,
  });
  const operations = journal.data?.operations ?? [];
  // Same view for every model. Counters belong to the connection that reported them; a phone
  // without its own counters shows a mounted volume only after the user links it explicitly.
  const linked = useLinkedVolume(selected, devices.data?.devices ?? []);
  const space = storage(linked.volume);
  const backups = (workspace.data?.backups ?? []).filter((b) => typeof b.created === 'string');
  const lastBackup = backups
    .map((b) => String(b.created))
    .sort()
    .at(-1);
  const services = Object.entries(selected?.capability_status ?? {});
  const available = services.filter(([, s]) => s.status === 'available').length;
  const state = devices.isPending
    ? 'checking'
    : selected?.connected
      ? 'connected'
      : selected
        ? 'disconnected'
        : 'none';
  const profile = selected?.model_profile;
  // The connection did not identify the model: show the project's artwork, labelled as an illustration only.
  const [artwork, setArtwork] = useState<'e52' | 'e72'>('e52');
  const picture = profile
    ? { src: profile.image, alt: profile.name }
    : artwork === 'e72'
      ? { src: '/phones/nokia-e72.png', alt: 'Nokia E72' }
      : { src: '/phones/nokia-e52-silver.png', alt: 'Nokia E52' };
  const candidates = [
    {
      key: 'battery',
      icon: Battery,
      label: t('Battery', 'Заряд батареи'),
      value: selected?.battery != null ? `${selected.battery}%` : null,
      progress: selected?.battery ?? null,
      note: null,
    },
    {
      key: 'signal',
      icon: Signal,
      label: t('Signal', 'Уровень сигнала'),
      value: selected?.signal != null ? `${selected.signal}%` : null,
      progress: selected?.signal ?? null,
      note: null,
    },
    {
      key: 'free',
      icon: HardDrive,
      label: t('Free space', 'Свободно на накопителе'),
      value: space ? formatBytes(space.free) : null,
      progress: space ? 100 - space.usedPercent : null,
      note: space ? `${t('of', 'из')} ${formatBytes(space.total)}` : null,
    },
    {
      key: 'life',
      icon: Clock3,
      label: t('Life timer', 'Счётчик часов'),
      value:
        selected?.life_timer_hours != null
          ? `${selected.life_timer_hours.toFixed(1)} ${t('h', 'ч')}`
          : null,
      progress: null,
      note: null,
    },
    {
      key: 'services',
      icon: ActivityIcon,
      label: t('Connection services', 'Сервисы подключения'),
      value: services.length ? `${available} / ${services.length}` : null,
      progress: services.length ? (100 * available) / services.length : null,
      note: services.length ? t('available', 'доступно') : null,
    },
    {
      key: 'backup',
      icon: DatabaseBackup,
      label: t('Last server backup', 'Последняя копия'),
      value: lastBackup ? new Date(lastBackup).toLocaleDateString(locale) : null,
      progress: null,
      note: lastBackup
        ? `${backups.length} ${t('stored on the server', 'хранится на сервере')}`
        : t('No full backup yet', 'Полной копии ещё нет'),
    },
  ];
  const metrics = candidates;
  const updated = devices.dataUpdatedAt
    ? new Date(devices.dataUpdatedAt).toLocaleTimeString(locale, {
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;
  return (
    <Stack spacing={2} className="mui-dashboard">
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        flexWrap="wrap"
        gap={1}
      >
        <Typography variant="h1" component="h1" sx={{ fontSize: 26, fontWeight: 600, m: 0 }}>
          {t('Device overview', 'Обзор устройства')}
        </Typography>
        <Stack direction="row" alignItems="center" spacing={1}>
          {updated && (
            <Typography variant="body2" color="text.secondary">
              {t('Checked', 'Проверено')}: {updated}
            </Typography>
          )}
          <Button
            size="small"
            variant="outlined"
            startIcon={<RefreshCw size={14} aria-hidden="true" />}
            disabled={devices.isFetching}
            onClick={() => {
              void devices.refetch();
            }}
          >
            {t('Refresh', 'Обновить')}
          </Button>
        </Stack>
      </Stack>
      {devices.error && (
        <Typography role="alert" color="error">
          {devices.error.message}
        </Typography>
      )}

      <Card
        sx={{
          background: (th) =>
            `linear-gradient(120deg, ${th.palette.mode === 'dark' ? '#1d3150' : '#e9f0fb'} 0%, ${th.palette.background.paper} 70%)`,
        }}
      >
        <CardContent sx={{ p: { xs: 2, md: 3 } }}>
          <Box
            sx={{
              display: 'grid',
              gap: 3,
              alignItems: 'center',
              gridTemplateColumns: {
                xs: '1fr',
                md: '170px minmax(0,1fr) 200px',
              },
            }}
          >
            <Stack alignItems="center" spacing={0.75}>
              <Box
                component="img"
                src={`${base}${picture.src.replace(/^\//, '')}`}
                alt={
                  profile
                    ? picture.alt
                    : t('Illustration (model not identified)', 'Иллюстрация (модель не определена)')
                }
                sx={{
                  height: 200,
                  maxWidth: '100%',
                  objectFit: 'contain',
                  opacity: profile ? 1 : 0.85,
                }}
              />
              {!profile && (
                <Stack alignItems="center" spacing={0.5}>
                  <Typography variant="caption" color="text.secondary" align="center">
                    {t(
                      'Illustration only — the connection did not report a model',
                      'Только иллюстрация — подключение не сообщило модель',
                    )}
                  </Typography>
                  <Stack direction="row" spacing={0.5}>
                    {(['e52', 'e72'] as const).map((id) => (
                      <Chip
                        key={id}
                        size="small"
                        label={id.toUpperCase()}
                        clickable
                        color={artwork === id ? 'primary' : 'default'}
                        variant={artwork === id ? 'filled' : 'outlined'}
                        onClick={() => setArtwork(id)}
                        aria-pressed={artwork === id}
                      />
                    ))}
                  </Stack>
                </Stack>
              )}
            </Stack>
            <Stack spacing={1.5} sx={{ minWidth: 0 }}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                <StateChip state={state} />
                {selected?.evidence && (
                  <Typography variant="caption" color="text.secondary">
                    {selected.evidence}
                  </Typography>
                )}
              </Stack>
              <Typography variant="h2" component="h2" sx={{ fontSize: 30, fontWeight: 700, m: 0 }}>
                {profile?.name ??
                  selected?.model ??
                  selected?.name ??
                  t('Symbian phone', 'Телефон Symbian')}
              </Typography>
              <Typography color="text.secondary">
                {profile
                  ? `Symbian ${profile.symbian} · S60 ${profile.s60} · ${profile.screen.width}×${profile.screen.height} (${profile.screen.orientation === 'landscape' ? t('landscape', 'альбомная') : t('portrait', 'книжная')})`
                  : t(
                      'Model profile is not available for this connection.',
                      'Профиль модели для этого подключения недоступен.',
                    )}
              </Typography>
              <Box
                sx={{
                  display: 'grid',
                  gap: 2,
                  gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))',
                }}
              >
                <Fact
                  icon={Cpu}
                  label={t('Firmware', 'Прошивка')}
                  value={selected?.firmware}
                  extra={selected?.rm ? `RM ${selected.rm}` : null}
                />
                <Fact
                  icon={HardDrive}
                  label={t('Storage', 'Накопитель')}
                  value={space ? formatBytes(space.total) : null}
                  extra={space ? `${t('free', 'свободно')} ${formatBytes(space.free)}` : null}
                />
                <Fact
                  icon={Usb}
                  label={t('Transport', 'Транспорт')}
                  value={selected?.transport}
                  extra={selected?.usb_mode ? `USB: ${selected.usb_mode}` : null}
                />
              </Box>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Button
                  variant="contained"
                  startIcon={<FolderOpen size={16} aria-hidden="true" />}
                  href="#phone/files"
                >
                  {t('Files', 'Файлы')}
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Users size={16} aria-hidden="true" />}
                  href="#phone/contacts"
                >
                  {t('Contacts', 'Контакты')}
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<DatabaseBackup size={16} aria-hidden="true" />}
                  href="#phone/backups"
                >
                  {t('Backup', 'Резервная копия')}
                </Button>
              </Stack>
            </Stack>
            <Box
              sx={{
                display: { xs: 'none', md: 'grid' },
                placeItems: 'center',
                borderLeft: 1,
                borderColor: 'divider',
                pl: 3,
                height: '100%',
              }}
            >
              <Box
                component="img"
                src={`${base}brand/${useTheme().palette.mode === 'dark' ? 'nokia-white' : 'nokia-blue'}.svg`}
                alt="Nokia"
                sx={{ width: 150 }}
              />
              <Typography
                variant="h3"
                sx={{ fontSize: 28, fontWeight: 700, color: 'primary.main' }}
              >
                {profile?.name.replace(/^Nokia\s*/i, '') ??
                  selected?.model?.replace(/^Nokia\s*/i, '') ??
                  ''}
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>

      <Box
        sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))' }}
      >
        {metrics.map((m) => (
          <Metric {...m} key={m.key} />
        ))}
      </Box>
      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: '1fr', lg: 'minmax(0,1fr) minmax(0,1.4fr)' },
        }}
      >
        <Panel
          title={t('Storage', 'Хранилище')}
          subtitle={space ? `${t('Total', 'Всего')}: ${formatBytes(space.total)}` : undefined}
        >
          <Stack direction={{ xs: 'column', sm: 'row' }} alignItems="center" spacing={2}>
            <PieChart
              width={190}
              height={190}
              hideLegend
              margin={{ top: 4, bottom: 4, left: 4, right: 4 }}
              series={[
                {
                  innerRadius: 62,
                  outerRadius: 90,
                  paddingAngle: space ? 2 : 0,
                  cornerRadius: 3,
                  data: space
                    ? [
                        {
                          id: 'used',
                          value: space.used,
                          label: t('Used', 'Занято'),
                          color: usedColor,
                        },
                        {
                          id: 'free',
                          value: space.free,
                          label: t('Free', 'Свободно'),
                          color: freeColor,
                        },
                      ]
                    : [
                        {
                          id: 'none',
                          value: 1,
                          label: t('No data', 'Нет данных'),
                          color: emptyColor,
                        },
                      ],
                  valueFormatter: (item) => (space ? formatBytes(item.value) : '—'),
                },
              ]}
            />
            <Stack spacing={1.5}>
              <Legend
                color={usedColor}
                label={t('Used', 'Занято')}
                value={space ? `${formatBytes(space.used)} (${space.usedPercent}%)` : '—'}
              />
              <Legend
                color={freeColor}
                label={t('Free', 'Свободно')}
                value={space ? `${formatBytes(space.free)} (${100 - space.usedPercent}%)` : '—'}
              />
              <Typography variant="caption" color="text.secondary">
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
              </Typography>
              {linked.candidates.length > 0 && selected && (
                <label>
                  <Typography variant="caption" color="text.secondary" component="span">
                    {t('Link a memory card volume', 'Связать с томом карты памяти')}{' '}
                  </Typography>
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
            </Stack>
          </Stack>
        </Panel>
        <Panel
          title={t('SymPort operations, 7 days', 'Операции SymPort за 7 дней')}
          subtitle={`${operations.length} ${t('in the log', 'в журнале')}`}
        >
          <DayChart operations={operations} />
          {!operations.length && (
            <Typography variant="caption" color="text.secondary">
              {t('No operations recorded yet.', 'Операций пока не записано.')}
            </Typography>
          )}
        </Panel>
      </Box>

      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: '1fr', lg: 'repeat(3,minmax(0,1fr))' },
        }}
      >
        <Panel title={t('Quick actions', 'Быстрые действия')}>
          <Box
            sx={{
              display: 'grid',
              gap: 1,
              gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))',
            }}
          >
            {(
              [
                [
                  FolderOpen,
                  t('Open files', 'Открыть файлы'),
                  t('Browse the storage', 'Просмотр накопителя'),
                  '#phone/files',
                ],
                [
                  DatabaseBackup,
                  t('Create backup', 'Создать копию'),
                  t('Full card backup', 'Полная копия карты'),
                  '#phone/backups',
                ],
                [
                  AppWindow,
                  t('Install app', 'Установить приложение'),
                  t('SIS / SISX transfer', 'Передача SIS / SISX'),
                  '#apps/installed',
                ],
                [
                  PackageSearch,
                  t('Check package', 'Проверить пакет'),
                  t('Certificates, dependencies', 'Сертификаты, зависимости'),
                  '#tools/certificates',
                ],
              ] as [LucideIcon, string, string, string][]
            ).map(([Icon, title, hint, href]) => (
              <ButtonBase
                key={href}
                href={href}
                sx={{
                  display: 'flex',
                  justifyContent: 'flex-start',
                  alignItems: 'center',
                  gap: 1.25,
                  p: 1.25,
                  textAlign: 'left',
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  '&:hover': { borderColor: 'primary.main', bgcolor: 'action.hover' },
                }}
              >
                <Box sx={{ color: 'primary.main', display: 'grid' }}>
                  <Icon size={22} aria-hidden="true" />
                </Box>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="body2" fontWeight={600}>
                    {title}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" component="div">
                    {hint}
                  </Typography>
                </Box>
              </ButtonBase>
            ))}
          </Box>
        </Panel>
        <Panel title={t('Device state', 'Состояние устройства')}>
          <StateList
            rows={[
              [
                t('Connection', 'Подключение'),
                state === 'connected' ? 'ok' : state === 'checking' ? 'unknown' : 'warn',
                state === 'connected'
                  ? t('Connected', 'Подключено')
                  : state === 'checking'
                    ? t('Checking…', 'Проверка…')
                    : t('No device', 'Нет устройства'),
              ],
              [
                t('File access', 'Доступ к файлам'),
                selected?.capability_matrix?.['files.list']?.status === 'available'
                  ? 'ok'
                  : 'unknown',
                selected?.capability_matrix?.['files.list']?.status === 'available'
                  ? t('Verified', 'Проверено')
                  : selected?.capability_matrix?.['files.list']?.status === 'unsupported'
                    ? t('Not supported by this connection', 'Это подключение не поддерживает')
                    : t('Not verified', 'Не проверено'),
              ],
              [
                t('Firmware vs reference', 'Прошивка и справочник'),
                selected?.firmware_update?.status === 'older'
                  ? 'warn'
                  : selected?.firmware_update?.status === 'current-in-reference'
                    ? 'ok'
                    : 'unknown',
                selected?.firmware_update?.status === 'older'
                  ? `${t('newer listed', 'есть новее')}: ${selected.firmware_update.latest_known ?? ''}`
                  : selected?.firmware_update?.status === 'current-in-reference'
                    ? t('matches reference', 'по справочнику')
                    : t('No data', 'Нет данных'),
              ],
              [
                t('USB mode', 'USB-режим'),
                selected?.usb_mode ? 'ok' : 'unknown',
                selected?.usb_mode ?? t('No data', 'Нет данных'),
              ],
              [
                t('Full backup', 'Полная копия'),
                lastBackup ? 'ok' : 'warn',
                lastBackup ? new Date(lastBackup).toLocaleString(locale) : t('None yet', 'Ещё нет'),
              ],
            ]}
          />
        </Panel>
        <Panel
          title={t('Device log', 'Журнал устройства')}
          action={
            <Button size="small" href="#tools/activity">
              {t('Show all', 'Показать все')}
            </Button>
          }
        >
          {operations.length ? (
            <Stack spacing={1.25}>
              {operations
                .slice(-6)
                .reverse()
                .map((op, index) => (
                  <Stack
                    direction="row"
                    spacing={1.25}
                    alignItems="center"
                    key={`${op.time}-${index}`}
                  >
                    <Box
                      sx={{
                        color: op.status === 'success' ? 'success.main' : 'warning.main',
                        display: 'grid',
                      }}
                    >
                      <History size={18} aria-hidden="true" />
                    </Box>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="body2" fontWeight={600} noWrap>
                        {op.action}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {op.status}
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      {timeLabel(op.time, locale)}
                    </Typography>
                  </Stack>
                ))}
            </Stack>
          ) : (
            <NoData text={t('Nothing recorded yet.', 'Пока ничего не записано.')} />
          )}
        </Panel>
      </Box>

      {selected?.capability_matrix ? (
        <Stack spacing={0.75}>
          <Typography variant="caption" color="text.secondary">
            {t(
              'Verified by a read-only probe of this connection (details: Connection):',
              'Подтверждено безопасной проверкой чтения этого подключения (подробнее: «Подключение»):',
            )}
          </Typography>
          <Stack
            direction="row"
            spacing={0.75}
            flexWrap="wrap"
            useFlexGap
            aria-label={t('Verified capabilities', 'Подтверждённые возможности')}
          >
            {Object.entries(selected.capability_matrix)
              .filter(([, s]) => s.status === 'available')
              .map(([op]) => (
                <Chip key={op} size="small" variant="outlined" label={op} />
              ))}
            {!Object.values(selected.capability_matrix).some((s) => s.status === 'available') && (
              <Chip
                size="small"
                variant="outlined"
                label={t('Nothing verified yet', 'Пока ничего не подтверждено')}
              />
            )}
          </Stack>
        </Stack>
      ) : null}
    </Stack>
  );
}

function StateChip({ state }: { state: 'checking' | 'connected' | 'disconnected' | 'none' }) {
  const { t } = usePreferences();
  const text = {
    checking: t('Checking…', 'Проверка…'),
    connected: t('Connected', 'Подключено'),
    disconnected: t('Disconnected', 'Отключено'),
    none: t('No device', 'Нет устройства'),
  }[state];
  return (
    <Chip
      size="small"
      label={text}
      color={state === 'connected' ? 'success' : state === 'checking' ? 'default' : 'warning'}
      variant={state === 'connected' ? 'filled' : 'outlined'}
    />
  );
}

function Fact({
  icon: Icon,
  label,
  value,
  extra,
}: {
  icon: LucideIcon;
  label: string;
  value: string | null | undefined;
  extra?: string | null | undefined;
}) {
  const { t } = usePreferences();
  return (
    <Stack direction="row" spacing={1.25} alignItems="flex-start" sx={{ minWidth: 0 }}>
      <Box sx={{ color: 'primary.main', mt: 0.5 }}>
        <Icon size={22} aria-hidden="true" />
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <Typography fontWeight={600} noWrap>
          {value || <span className="value-state--unknown">ⓘ {t('No data', 'Нет данных')}</span>}
        </Typography>
        {extra && (
          <Typography variant="caption" color="text.secondary" noWrap component="div">
            {extra}
          </Typography>
        )}
      </Box>
    </Stack>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  progress,
  note,
}: {
  icon: LucideIcon;
  label: string;
  value: string | null;
  progress?: number | null;
  note?: string | null;
}) {
  const { t } = usePreferences();
  return (
    <Card>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Box
            sx={{
              display: 'grid',
              placeItems: 'center',
              width: 40,
              height: 40,
              borderRadius: 1,
              bgcolor: 'action.hover',
              color: 'primary.main',
              flex: 'none',
            }}
          >
            <Icon size={20} aria-hidden="true" />
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary" noWrap component="div">
              {label}
            </Typography>
            <Typography variant="h6" component="div" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
              {value ?? <span aria-label={t('No data', 'Нет данных')}>—</span>}
            </Typography>
          </Box>
        </Stack>
        {progress != null && progress >= 0 && progress <= 100 && (
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{ mt: 1.5, height: 6, borderRadius: 3 }}
            aria-label={label}
          />
        )}
        {(note ??
          (value === null
            ? t('Not reported by this transport', 'Не сообщается транспортом')
            : null)) && (
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.75 }}>
            {note ?? t('Not reported by this transport', 'Не сообщается транспортом')}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

function Panel({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string | undefined;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Card component="section" sx={{ minWidth: 0 }}>
      <CardContent sx={{ p: 2.5 }}>
        <Stack
          direction="row"
          alignItems="baseline"
          justifyContent="space-between"
          sx={{ mb: 1.5 }}
        >
          <Typography variant="h3" component="h3" sx={{ fontSize: 16, fontWeight: 600, m: 0 }}>
            {title}
          </Typography>
          {action ??
            (subtitle && (
              <Typography variant="caption" color="text.secondary">
                {subtitle}
              </Typography>
            ))}
        </Stack>
        {children}
      </CardContent>
    </Card>
  );
}

function Legend({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Box sx={{ width: 12, height: 12, borderRadius: 0.5, bgcolor: color }} />
      <Box>
        <Typography variant="body2" fontWeight={600}>
          {label}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {value}
        </Typography>
      </Box>
    </Stack>
  );
}

function NoData({ text }: { text: string }) {
  return (
    <Typography color="text.secondary" sx={{ py: 3 }}>
      {text}
    </Typography>
  );
}

function StateList({ rows }: { rows: [string, 'ok' | 'warn' | 'unknown', string][] }) {
  return (
    <Stack divider={<Box sx={{ borderTop: 1, borderColor: 'divider' }} />} spacing={1}>
      {rows.map(([label, tone, text]) => (
        <Stack
          key={label}
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          spacing={1}
          sx={{ pt: 1 }}
        >
          <Typography variant="body2" fontWeight={600}>
            {label}
          </Typography>
          <Chip
            size="small"
            variant="outlined"
            color={tone === 'ok' ? 'success' : tone === 'warn' ? 'warning' : 'default'}
            label={text}
            sx={{ maxWidth: '60%' }}
          />
        </Stack>
      ))}
    </Stack>
  );
}

function DayChart({
  operations,
}: {
  operations: { time: string; action: string; status: string }[];
}) {
  const { t } = usePreferences();
  const usedColor = useTheme().palette.primary.main;
  const days = perDay(operations);
  return (
    <BarChart
      height={220}
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
        {
          data: days.map((d) => d.ok),
          label: t('Succeeded', 'Успешно'),
          stack: 'ops',
          color: usedColor,
        },
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
