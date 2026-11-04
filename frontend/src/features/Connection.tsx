import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { keys, useDevices } from '../api/queries';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
export default function Connection() {
  const api = useApi();
  const queryClient = useQueryClient();
  const { t, device, setDevice } = usePreferences();
  const devices = useDevices();
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
        </Card>
      ))}
    </>
  );
}
