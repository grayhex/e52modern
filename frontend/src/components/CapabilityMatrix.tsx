import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi, usePreferences } from '../state/app';
import { keys } from '../api/queries';
import { ATTEMPT_TEXT, SERVICES, STATUS_TEXT } from '../api/capabilities';
import type { Device } from '../api/contracts';
import { ErrorMessage } from './ui';

function time(value: string, language: 'ru' | 'en') {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleString(language === 'en' ? 'en-GB' : 'ru-RU', {
        dateStyle: 'short',
        timeStyle: 'medium',
      });
}

/**
 * What this very connection can do, where each answer comes from and when it was checked.
 * “Verified” needs a successful safe probe of that connection; writes are never probed.
 * Rechecking reads only (identity, store status, folder listing) and replaces the cached row.
 */
export default function CapabilityMatrix({ device }: { device: Device }) {
  const api = useApi();
  const cache = useQueryClient();
  const { t, language } = usePreferences();
  const recheck = useMutation({
    mutationFn: () => api.recheck(device.id),
    onSuccess: ({ device: fresh }) => {
      cache.setQueryData(keys.devices, (old: { devices: Device[] } | undefined) =>
        old ? { ...old, devices: old.devices.map((d) => (d.id === fresh.id ? fresh : d)) } : old,
      );
    },
  });
  const matrix = device.capability_matrix;
  return (
    <section aria-label={t('Connection capabilities', 'Возможности подключения')}>
      <div className="form-row">
        <button
          type="button"
          className="btn secondary"
          disabled={recheck.isPending}
          onClick={() => recheck.mutate()}
        >
          {recheck.isPending
            ? t('Checking…', 'Проверка…')
            : t('Recheck (read-only)', 'Перепроверить (только чтение)')}
        </button>
        {device.capabilities_checked_at && (
          <small>
            {t('Last checked', 'Проверено')}: {time(device.capabilities_checked_at, language)}
          </small>
        )}
      </div>
      <ErrorMessage error={recheck.error} />
      {!matrix ? (
        <p className="note">
          {t(
            'This component did not report probe results, so no service is treated as available.',
            'Компонент не прислал результаты проверок, поэтому ни одна служба не считается доступной.',
          )}
        </p>
      ) : (
        SERVICES.map((service) => (
          <details key={service.id} open={service.id !== 'software'}>
            <summary>{t(service.en, service.ru)}</summary>
            <table className="capability-table">
              <thead>
                <tr>
                  <th scope="col">{t('Operation', 'Операция')}</th>
                  <th scope="col">{t('State', 'Состояние')}</th>
                  <th scope="col">{t('Where it comes from', 'Откуда известно')}</th>
                </tr>
              </thead>
              <tbody>
                {service.ops.map(([op, en, ru]) => {
                  const state = matrix[op];
                  if (!state) return null;
                  const [statusEn, statusRu] = STATUS_TEXT[state.status];
                  const [attemptEn, attemptRu] = ATTEMPT_TEXT[state.attempt];
                  return (
                    <tr key={op} data-op={op} data-status={state.status}>
                      <th scope="row">
                        {t(en, ru)}
                        <small className="capability-mode">
                          {state.mode === 'write' ? t('write', 'запись') : t('read', 'чтение')}
                        </small>
                      </th>
                      <td>
                        <span className={`chip capability-chip capability-chip--${state.status}`}>
                          {t(statusEn, statusRu)}
                        </span>
                        {state.status === 'not-tested' && state.attempt !== 'blocked' && (
                          <small> {t(attemptEn, attemptRu)}</small>
                        )}
                      </td>
                      <td>
                        {state.evidence}
                        <small className="capability-source">
                          {' '}
                          · {state.source} · {time(state.checked_at, language)}
                        </small>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </details>
        ))
      )}
    </section>
  );
}
