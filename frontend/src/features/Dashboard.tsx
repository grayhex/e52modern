import { useQuery } from '@tanstack/react-query';
import { useDevices, keys } from '../api/queries';
import { useApi, usePreferences } from '../state/app';
import { Card, ErrorMessage, Reading } from '../components/ui';
export default function Dashboard() {
  const { data, error, isFetching } = useDevices();
  const api = useApi();
  const { device, t } = usePreferences();
  const selected =
    data?.devices.find((d) => d.id === device) ??
    data?.devices.find((d) => d.connected && d.model) ??
    data?.devices[0];
  const journal = useQuery({
    queryKey: keys.history,
    queryFn: ({ signal }) => api.history(signal),
    refetchInterval: 30000,
  });
  return (
    <>
      <h1>{t('Dashboard', 'Обзор телефона')}</h1>
      <ErrorMessage error={error} />
      <Card className="dashboard-hero">
        <div className="phone-dashboard">
          {selected?.model_profile && (
            <img
              className="dashboard-phone"
              src={`${import.meta.env.BASE_URL}${selected.model_profile.image.replace(/^\//, '')}`}
              alt={selected.model_profile.name}
            />
          )}
          <div>
            <div className="dashboard-title">
              <h2>{selected?.model ?? t('Symbian phone', 'Телефон Symbian')}</h2>
              <span
                className={`device-value value-state--${selected?.connected ? 'connected' : 'unknown'}`}
              >
                {isFetching
                  ? t('Reading…', 'Чтение…')
                  : selected?.connected
                    ? t('Connected', 'Подключено')
                    : t('No device', 'Нет устройства')}
              </span>
            </div>
            {selected?.model_profile && (
              <p>
                {selected.model_profile.symbian} · S60 {selected.model_profile.s60} ·{' '}
                {selected.model_profile.screen.width} × {selected.model_profile.screen.height}
              </p>
            )}
            <dl className="dashboard-grid">
              {[
                [t('Model', 'Модель'), selected?.model],
                ['RM', selected?.rm],
                [t('Firmware', 'Прошивка'), selected?.firmware],
                [
                  t('Battery', 'Батарея'),
                  selected?.battery == null ? null : `${selected.battery}%`,
                ],
                [t('Signal', 'Сигнал'), selected?.signal == null ? null : `${selected.signal}%`],
                [
                  t('Free memory', 'Свободная память'),
                  selected?.free == null ? null : `${(selected.free / 1024 ** 2).toFixed(1)} MiB`,
                ],
                ['IMEI', selected?.imei],
                [t('Transport', 'Транспорт'), selected?.transport],
                [t('USB mode', 'USB-режим'), selected?.usb_mode],
                [
                  t('Capacity', 'Ёмкость'),
                  selected?.total == null ? null : `${(selected.total / 1024 ** 3).toFixed(1)} GiB`,
                ],
                [
                  t('Life timer', 'Счётчик часов'),
                  selected?.life_timer_hours == null
                    ? null
                    : `${selected.life_timer_hours.toFixed(1)} h`,
                ],
              ].map(([label, value]) => (
                <div className="dashboard-metric" key={label}>
                  <dt>{label}</dt>
                  <dd>
                    <Reading value={value} />
                  </dd>
                </div>
              ))}
            </dl>
            {selected?.firmware_update?.status === 'older' && (
              <p className="device-value value-state--warning">
                ↗ {t('Update listed in Updates', 'В разделе «Обновления» есть новая версия')}:{' '}
                {selected.firmware_update.latest_known}
              </p>
            )}
            {selected?.life_timer_hours == null && (
              <p className="muted">{selected?.life_timer_reason}</p>
            )}
            <div className="dashboard-grid">
              {(
                [
                  ['Battery', 'Батарея', selected?.battery],
                  ['Signal', 'Сигнал', selected?.signal],
                ] as const
              ).map(([en, ru, value]) =>
                value != null && value >= 0 && value <= 100 ? (
                  <progress key={en} max={100} value={value} aria-label={t(en, ru)} />
                ) : null,
              )}
            </div>
            <div className="dashboard-capabilities">
              {selected?.capabilities.map((cap) => (
                <span className="chip" key={cap}>
                  {cap}
                </span>
              ))}
            </div>
            {selected?.capability_status && (
              <details>
                <summary>{t('Connection services', 'Сервисы подключения')}</summary>
                {Object.entries(selected.capability_status).map(([name, status]) => (
                  <p key={name}>
                    {name} ·{' '}
                    <span
                      className={`device-value value-state--${status.status === 'available' ? 'available' : 'warning'}`}
                    >
                      {status.status === 'available'
                        ? t('Available', 'Доступно')
                        : t('Unavailable', 'Недоступно')}
                    </span>{' '}
                    {status.reason}
                  </p>
                ))}
              </details>
            )}
          </div>
        </div>
      </Card>
      <Card>
        <h2>{t('Device log', 'Журнал устройства')}</h2>
        <ErrorMessage error={journal.error} />
        <div className="scroll-y">
          {journal.data?.operations
            .slice()
            .reverse()
            .map((row, index) => (
              <p key={`${row.time}-${index}`}>
                {row.time} · {row.action} · {row.status}
              </p>
            ))}
        </div>
      </Card>
    </>
  );
}
