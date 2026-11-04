import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChartFrame } from '../components/ChartFrame';
import { ChartTheme } from '../dashboard/ChartTheme';
import { useTheme } from '@mui/material/styles';
import { LineChart } from '@mui/x-charts/LineChart';
import { useApi, usePreferences } from '../state/app';
import { useDevices } from '../api/queries';
import { measurementsSchema } from '../api/p1';
import { fileSchema, objectSchema } from '../api/workspace';
import { Card, DeviceSelect, ErrorMessage, Reading } from '../components/ui';
import { Download } from '../components/workspace';
import { bytes } from '../utils/files';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
export default function Telemetry() {
  const { t, device, setDevice } = usePreferences();
  return (
    <>
      <Card>
        <div className="card-head">
          <h2>{t('Device measurements', 'Измерения устройства')}</h2>
          <span className="chip">Nokia S60</span>
        </div>
        <DeviceSelect
          value={device}
          onChange={setDevice}
          label={t('Measurement connection', 'Подключение для измерений')}
        />
      </Card>
      {device ? (
        <ChartTheme>
          <Measurements key={device} device={device} />
        </ChartTheme>
      ) : (
        <Card>
          <p>
            {t(
              'Choose a connection in Settings. On Windows, start Bridge, allow this SymPort address, then connect Nokia in PC Suite mode.',
              'Выберите подключение в настройках. На Windows запустите Bridge, разрешите адрес SymPort и подключите Nokia в режиме PC Suite.',
            )}
          </p>
          <a className="btn secondary" href="#phone/connection">
            {t('Connection settings', 'Настройки подключения')}
          </a>
        </Card>
      )}
    </>
  );
}
function Measurements({ device }: { device: string }) {
  const chartPalette = useTheme().palette;
  const api = useApi(),
    cache = useQueryClient(),
    { t } = usePreferences(),
    devices = useDevices(),
    phone = devices.data?.devices.find((d) => d.id === device),
    [automatic, setAutomatic] = useState(false),
    [series, setSeries] = useState('');
  const confirm = useConfirmedAction<string>();
  const history = useQuery({
    queryKey: ['diagnostics', device],
    queryFn: ({ signal }) =>
      api.request('/api/diagnostics', { action: 'history', device }, measurementsSchema, signal),
  });
  const sample = useMutation({
    mutationFn: () =>
      api.request('/api/diagnostics', { action: 'sample', device }, measurementsSchema),
    onSuccess: (result) => cache.setQueryData(['diagnostics', device], result),
  });
  const exported = useMutation({
    mutationFn: (format: string) =>
      api.request('/api/diagnostics', { action: 'export', device, format }, fileSchema),
  });
  const { isPending: sampling, mutate: takeSample } = sample;
  useEffect(() => {
    if (!automatic) return;
    const timer = setInterval(() => {
      if (!sampling) takeSample();
    }, 15000);
    return () => clearInterval(timer);
  }, [automatic, sampling, takeSample]);
  const rows = history.data?.measurements ?? [],
    latest = rows.at(-1),
    activeSeries = series || latest?.series,
    visible = rows.filter((r) => r.series === activeSeries),
    hasPercent = visible.some((r) => r.battery !== null || r.signal !== null),
    hasMemory = visible.some((r) => r.free !== null);
  return (
    <>
      <Card>
        <div className="form-row">
          <button
            className="btn primary"
            disabled={sample.isPending || !phone}
            onClick={() => sample.mutate()}
          >
            {sample.isPending
              ? t('Reading adapter…', 'Чтение адаптера…')
              : t('Read measurements', 'Прочитать показатели')}
          </button>
          <label className="p1-consent">
            <input
              type="checkbox"
              checked={automatic}
              onChange={(e) => setAutomatic(e.target.checked)}
            />
            {t(
              'Record every 15 seconds while this page is open',
              'Записывать каждые 15 секунд, пока раздел открыт',
            )}
          </label>
          {['json', 'csv'].map((format) => (
            <button
              key={format}
              className="btn secondary"
              disabled={!rows.length || exported.isPending}
              onClick={() => exported.mutate(format)}
            >
              {t('Export', 'Экспорт')} {format.toUpperCase()}
            </button>
          ))}
          <button
            className="btn ghost"
            disabled={!rows.length}
            onClick={() =>
              confirm.ask(
                t(
                  'Delete diagnostic history for this connection? Phone data is unaffected.',
                  'Удалить историю измерений этого подключения? Данные телефона не затрагиваются.',
                ),
                device,
              )
            }
          >
            {t('Clear history', 'Очистить историю')}
          </button>
        </div>
        <p className="note">
          {t(
            'Only values returned by the adapter are recorded. Missing readings remain gaps, and a mounted drive measures storage rather than the phone battery or RAM. No IMEI or personal phone data is included.',
            'Записываются только значения адаптера. Отсутствующие показания остаются пропусками; смонтированный накопитель сообщает об объёме хранилища, а не о батарее или ОЗУ телефона. IMEI и личные данные не включаются.',
          )}
        </p>
        <ErrorMessage error={history.error ?? sample.error ?? exported.error} />
        {exported.data && <Download {...exported.data} />}
        <dl className="dashboard-grid">
          {[
            [t('Model', 'Модель'), latest?.model],
            ['RM', latest?.rm],
            [t('Firmware', 'Прошивка'), latest?.firmware],
            [t('Battery', 'Батарея'), latest?.battery == null ? null : `${latest.battery}%`],
            [t('Signal', 'Сигнал'), latest?.signal == null ? null : `${latest.signal}%`],
            [
              t('Storage free', 'Свободно в хранилище'),
              latest?.free == null ? null : bytes(latest.free),
            ],
            [t('Capacity', 'Ёмкость'), latest?.total == null ? null : bytes(latest.total)],
            [
              t('Life timer', 'Счётчик часов'),
              latest?.life_timer_hours == null ? null : `${latest.life_timer_hours} h`,
            ],
            [t('USB mode', 'USB-режим'), latest?.usb_mode],
            [
              t('Connection', 'Подключение'),
              latest
                ? latest.connected
                  ? t('Connected', 'Подключено')
                  : t('Disconnected', 'Отключено')
                : null,
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
        {latest && (
          <>
            <p>
              {t('Observed at', 'Время измерения')}: {new Date(latest.time).toLocaleString()}
            </p>
            <div className="dashboard-capabilities">
              {latest.capabilities.map((c) => (
                <span className="chip" key={c}>
                  {c}
                </span>
              ))}
            </div>
            {Object.entries(latest.capability_status).map(([name, s]) => (
              <p key={name}>
                {name} · {s.status}
              </p>
            ))}
            {latest.reasons.map((reason) => (
              <p className="note" key={reason}>
                {reason}
              </p>
            ))}
          </>
        )}
      </Card>
      {rows.length > 0 && (
        <Card>
          <div className="card-head">
            <h2>{t('Measurement history', 'История измерений')}</h2>
            <span>{rows.length} / 500</span>
          </div>
          <label className="p1-consent">
            {t('Series (model / RM / firmware)', 'Серия (модель / RM / прошивка)')}
            <select value={activeSeries ?? ''} onChange={(e) => setSeries(e.target.value)}>
              {[...new Set(rows.map((r) => r.series))].map((key) => {
                const r = rows.find((r) => r.series === key);
                return (
                  <option value={key} key={key}>
                    {r?.model ?? t('Unknown model', 'Модель не определена')} · {r?.rm ?? '—'} ·{' '}
                    {r?.firmware ?? '—'} · {key.slice(0, 6)}
                  </option>
                );
              })}
            </select>
          </label>
          <ChartFrame>
            {(width) =>
              hasPercent ? (
                <LineChart
                  width={width}
                  height={230}
                  skipAnimation
                  xAxis={[
                    {
                      data: visible.map((r) => new Date(r.time)),
                      scaleType: 'time',
                      valueFormatter: (value) => new Date(value).toLocaleTimeString(),
                    },
                  ]}
                  yAxis={[{ min: 0, max: 100, label: '%' }]}
                  series={[
                    {
                      data: visible.map((r) => r.battery),
                      label: t('Battery', 'Батарея'),
                      color: chartPalette.success.main,
                      connectNulls: false,
                    },
                    {
                      data: visible.map((r) => r.signal),
                      label: t('Signal', 'Сигнал'),
                      color: chartPalette.primary.main,
                      connectNulls: false,
                    },
                  ]}
                  grid={{ horizontal: true }}
                />
              ) : (
                <p className="empty">
                  {t(
                    'This adapter has not supplied battery or signal measurements.',
                    'Адаптер не предоставил измерения батареи или сигнала.',
                  )}
                </p>
              )
            }
          </ChartFrame>
          {hasMemory && (
            <ChartFrame>
              {(width) => (
                <LineChart
                  width={width}
                  height={210}
                  skipAnimation
                  xAxis={[{ data: visible.map((r) => new Date(r.time)), scaleType: 'time' }]}
                  yAxis={[{ label: 'MiB' }]}
                  series={[
                    {
                      data: visible.map((r) => (r.free == null ? null : r.free / 1024 ** 2)),
                      label: t('Storage free', 'Свободно в хранилище'),
                      color: chartPalette.mode === 'dark' ? '#c4b5fd' : '#7c3aed',
                      connectNulls: false,
                    },
                  ]}
                />
              )}
            </ChartFrame>
          )}
          <details>
            <summary>{t('Measurement table', 'Таблица измерений')}</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    {[
                      t('Time', 'Время'),
                      t('Battery', 'Батарея'),
                      t('Signal', 'Сигнал'),
                      t('Storage free', 'Свободное место'),
                    ].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visible
                    .slice()
                    .reverse()
                    .map((r) => (
                      <tr key={r.id}>
                        <td>{new Date(r.time).toLocaleString()}</td>
                        <td>
                          <Reading value={r.battery} />
                        </td>
                        <td>
                          <Reading value={r.signal} />
                        </td>
                        <td>
                          <Reading value={r.free == null ? null : bytes(r.free)} />
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </details>
        </Card>
      )}
      {confirm.dialog(async () => {
        setAutomatic(false);
        await api.request(
          '/api/diagnostics',
          { action: 'clear', device, confirm: true },
          objectSchema,
        );
        cache.setQueryData(['diagnostics', device], { measurements: [] });
      })}
    </>
  );
}
