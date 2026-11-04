import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { keys, useDevices } from '../api/queries';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
import CapabilityMatrix from '../components/CapabilityMatrix';
import ConnectionWizard from './ConnectionWizard';
import { objectSchema, text, entries, strings } from '../api/workspace';

export default function Connection() {
  const api = useApi();
  const queryClient = useQueryClient();
  const { t, device, setDevice } = usePreferences();
  const devices = useDevices();
  const [imei, setImei] = useState('');
  // Activity hides suspend effects: never retain a revealed identifier in a hidden view.
  useEffect(() => () => setImei(''), []);
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
    // Pairing lives in the wizard; this page only returns to the local transports.
    mutationFn: (kind: 'disconnect') => api.connection(kind),
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
      <ConnectionWizard />
      <Card>
        <h2>
          {t('After connecting: safe first steps', 'После подключения: безопасные первые шаги')}
        </h2>
        <ol className="p1-checklist">
          <li>
            <a href="#tools/diagnostics">{t('Read diagnostics', 'Прочитайте диагностику')}</a>
            {t(
              ': check model, RM, firmware and available services. A memory-card drive is a separate file-only connection.',
              ': проверьте модель, RM, прошивку и доступные службы. Накопитель карты — отдельное подключение только для файлов.',
            )}
          </li>
          <li>
            {t(
              'First read and export contacts, SMS and calendar where supported, then create backups. Review changes before writing.',
              'Сначала прочитайте и экспортируйте контакты, SMS и календарь, где это поддерживается, и создайте копии. Перед записью проверяйте план изменений.',
            )}
          </li>
          <li>
            {t(
              'For the first transfer choose a small file in a new folder. Read it back before sending a package. SIS installation is completed on the phone.',
              'Для первой передачи выберите небольшой файл в новой папке. Скачайте его обратно перед передачей пакетов. Установка SIS завершается на телефоне.',
            )}
          </li>
        </ol>
      </Card>
      <Card>
        <span className="chip">
          {state.data?.mode === 'direct'
            ? t('Local transports', 'Локальные транспорты')
            : state.data?.connected
              ? t('Connected', 'Подключено')
              : t('Disconnected', 'Отключено')}
        </span>
        <div className="form-row">
          <DeviceSelect
            value={device}
            onChange={(id) => {
              setImei('');
              setDevice(id);
            }}
          />
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
          <a className="btn ghost" href="#phone/connection">
            {t('Request access in the wizard above', 'Запрос доступа — в мастере выше')}
          </a>
        </div>
      </Card>
      <Card>
        <h2>{t('Local SymPort transports', 'Локальные транспорты SymPort')}</h2>
        <p>
          {t(
            'Connect USB and select PC Suite on Nokia. Mass Storage exposes the card only. Pair Bluetooth on the PC first; close Nokia Suite when it uses the same COM port. A remote SymPort server needs Windows Bridge for a phone connected to your PC.',
            'Подключите USB и выберите PC Suite на Nokia. Mass Storage открывает только карту. Сначала выполните сопряжение Bluetooth на ПК; закройте Nokia Suite, если она занимает тот же COM-порт. Для телефона на вашем ПК и удалённого сервера SymPort используйте Windows Bridge.',
          )}
        </p>
        <button
          className="btn secondary"
          disabled={action.isPending}
          onClick={() => action.mutate('disconnect')}
        >
          {t('Use local SymPort transports', 'Использовать локальные транспорты')}
        </button>
      </Card>
      {devices.data?.devices.map((row) => (
        <Card key={row.id}>
          <h2>{row.name ?? row.model ?? row.id}</h2>
          <p>{row.evidence}</p>
          <CapabilityMatrix device={row} />
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
