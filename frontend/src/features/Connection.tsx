import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { keys, useDevices } from '../api/queries';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
import { objectSchema, text, entries, strings } from '../api/workspace';

export default function Connection() {
  const api = useApi();
  const queryClient = useQueryClient();
  const { t, device, setDevice } = usePreferences();
  const devices = useDevices();
  const [imei, setImei] = useState('');
  const privateAction = useConfirmedAction<string>();
  const selected = devices.data?.devices.find((d) => d.id === device);
  useEffect(() => {
    const clear = () => setImei('');
    const timer = setTimeout(clear, 30000);
    addEventListener('blur', clear);
    return () => {
      clearTimeout(timer);
      removeEventListener('blur', clear);
    };
  }, [imei]);
  const diagnostics = useMutation({
    mutationFn: (id: string) =>
      api.request('/api/manager', { action: 'connection-diagnose', device: id }, objectSchema),
  });
  const host = useMutation({
    mutationFn: () => api.request('/api/manager', { action: 'connection-host' }, objectSchema),
  });
  const state = useQuery({
    queryKey: ['connection'],
    queryFn: ({ signal }) => api.connection('status', signal),
    refetchInterval: 20000,
    retry: false,
  });
  const action = useMutation({
    mutationFn: async (kind: 'pair' | 'disconnect') => {
      if (kind === 'disconnect') return api.connection('disconnect');
      const lease = await api.connection('enable');
      if (!lease.relay_token) throw Error('Missing bridge lease');
      try {
        const response = await fetch('http://127.0.0.1:24652/api/bridge/pair', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'omit',
          cache: 'no-store',
          redirect: 'error',
          signal: AbortSignal.timeout(90000),
          body: JSON.stringify({ origin: location.origin, token: lease.relay_token }),
        });
        const raw: unknown = await response.json();
        if (!response.ok || !z.object({ paired: z.literal(true) }).safeParse(raw).success)
          throw Error(t('Access was declined.', 'Доступ отклонён.'));
        return lease;
      } catch (error) {
        await api.connection('disconnect');
        throw error;
      }
    },
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: keys.devices });
      queryClient.removeQueries({ queryKey: ['files'] });
      queryClient.removeQueries({ queryKey: ['personal'] });
      queryClient.removeQueries({ queryKey: ['media'] });
      setDevice('');
      setImei('');
      await queryClient.invalidateQueries({ queryKey: ['connection'] });
    },
  });
  return (
    <>
      <h1>{t('Connection', 'Подключение')}</h1>
      <Card>
        <span className="chip">
          {state.data?.mode === 'direct'
            ? t('Local transports', 'Локальные транспорты')
            : state.data?.connected
              ? t('Connected', 'Подключено')
              : t('Disconnected', 'Отключено')}
        </span>
        <div className="form-row">
          <DeviceSelect value={device} onChange={setDevice} />
          <button
            className="btn primary"
            disabled={devices.isFetching}
            onClick={() => {
              void devices.refetch();
            }}
          >
            {t('Find phone', 'Найти телефон')}
          </button>
        </div>
        <ErrorMessage error={devices.error ?? state.error ?? action.error} />
        {selected?.capabilities.includes('device-details') && (
          <button
            className="btn ghost"
            onClick={() =>
              privateAction.ask(
                t('Reveal private IMEI for 30 seconds?', 'Показать личный IMEI на 30 секунд?'),
                device,
              )
            }
          >
            {t('Reveal IMEI', 'Показать IMEI')}
          </button>
        )}
        {imei && (
          <p>
            <code>{imei}</code>
          </p>
        )}
      </Card>
      <Card>
        <h2>Windows Bridge</h2>
        <p>
          {t(
            'Download and start the portable agent, then approve access on your Windows PC.',
            'Скачайте и запустите агент, затем подтвердите доступ на ПК с Windows.',
          )}
        </p>
        <div className="form-row">
          <a
            className="btn secondary"
            href="https://github.com/grayhex/e52modern/actions/workflows/windows-bridge.yml"
            target="_blank"
            rel="noreferrer"
          >
            {t('Download Bridge', 'Скачать Bridge')}
          </a>
          <button
            className="btn primary"
            disabled={action.isPending}
            onClick={() => action.mutate('pair')}
          >
            {t('Request access', 'Запросить доступ')}
          </button>
          <button
            className="btn ghost"
            disabled={action.isPending}
            onClick={() => action.mutate('disconnect')}
          >
            {t('Disconnect', 'Отключить')}
          </button>
        </div>
      </Card>
      {devices.data?.devices.map((row) => (
        <Card key={row.id}>
          <h2>{row.name ?? row.model ?? row.id}</h2>
          <p>{row.evidence}</p>
          <div className="dashboard-capabilities">
            {row.capabilities.map((cap) => (
              <span className="chip" key={cap}>
                {cap}
              </span>
            ))}
          </div>
          <button
            className="btn secondary"
            disabled={!row.connection_kind || diagnostics.isPending}
            onClick={() => diagnostics.mutate(row.id)}
          >
            {t('Diagnose connection', 'Диагностика подключения')}
          </button>
        </Card>
      ))}
      <Card>
        <button className="btn secondary" disabled={host.isPending} onClick={() => host.mutate()}>
          {t('Inspect host USB and Bluetooth', 'Проверить USB и Bluetooth компьютера')}
        </button>
        <ErrorMessage error={host.error ?? diagnostics.error} />
        {diagnostics.data && (
          <p>{text(objectSchema.catch({}).parse(diagnostics.data.connection).evidence)}</p>
        )}
        {host.data && (
          <>
            {['serial', 'bluetooth', 'volumes'].flatMap((kind) =>
              entries(host.data[kind]).map((candidate, i) => (
                <p key={`${kind}:${i}`}>
                  {kind} · {text(candidate.name) || text(candidate.port) || text(candidate.root)} ·{' '}
                  {text(candidate.address) || text(candidate.source)}
                </p>
              )),
            )}
            {strings(host.data.diagnostics).map((s) => (
              <p className="note" key={s}>
                {s}
              </p>
            ))}
          </>
        )}
        <p className="note">
          {t(
            'Host records are candidates. Select an enrolled connection to verify capabilities. Mass Storage exposes files only.',
            'Сведения компьютера — кандидаты. Выберите настроенное подключение для проверки возможностей. Mass Storage предоставляет только файлы.',
          )}
        </p>
      </Card>
      {privateAction.dialog(async (id) => {
        const result = await api.request(
          '/api/manager',
          { action: 'device-imei', device: id, confirm: true },
          z.object({ imei: z.string().nullish() }),
        );
        setImei(result.imei ?? '');
      })}
    </>
  );
}
