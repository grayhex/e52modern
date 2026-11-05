import { useWorkspace } from '../hooks/useWorkspace';
import { PageHeader } from '../components/kit';
import SettingsBackup from './SettingsBackup';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { bytes } from '../utils/files';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { objectSchema, text } from '../api/workspace';
import { useDevices } from '../api/queries';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
import { Field, JsonReport } from '../components/workspace';
const restoreSchema = z
  .object({
    applied: z.boolean(),
    plan: z.object({
      new: z.number(),
      identical: z.number(),
      conflict: z.number(),
      blocked: z.number(),
    }),
  })
  .catchall(z.json());
export default function Backups() {
  const api = useApi(),
    { t, device, setDevice } = usePreferences(),
    devices = useDevices(),
    cache = useQueryClient(),
    state = useWorkspace(),
    [id, setId] = useState(''),
    [only, setOnly] = useState(''),
    [planJob, setPlanJob] = useState<{ id: string; key: string } | null>(null),
    [consumed, setConsumed] = useState(false),
    confirm = useConfirmedAction<'create' | 'apply' | { delete: string }>();
  const key = JSON.stringify([id, device, only]),
    busy = state.data?.jobs.some((j) => j.status === 'running') ?? false,
    phone = devices.data?.devices.find((d) => d.id === device),
    local = phone?.transport === 'mounted-volume';
  const operation = useMutation({
    mutationFn: async (body: z.infer<typeof objectSchema>) =>
      api.request('/api/run', body, z.object({ id: z.string() })),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ['workspace'] });
    },
  });
  const completed =
    planJob?.key === key
      ? state.data?.jobs.find((j) => j.id === planJob.id && j.status === 'success')
      : null;
  const data = objectSchema.catch({}).parse(completed?.report?.data),
    restore = restoreSchema.safeParse(data.restore),
    plan = restore.success && !restore.data.applied ? restore.data.plan : null;
  return (
    <>
      <PageHeader title={t('Backups', 'Резервные копии')} />
      <Card>
        <p>
          {t('Server free space', 'Свободно на сервере')}: {bytes(state.data?.backup_free)}
        </p>
        <div className="form-row">
          <DeviceSelect value={device} onChange={setDevice} capability="files" />
          <button
            className="btn primary"
            disabled={!device || !local || busy || confirm.busy}
            onClick={() =>
              confirm.ask(
                t(
                  'Back up all accessible files? Other server jobs are blocked while copying.',
                  'Скопировать доступные файлы? Во время копирования другие задачи сервера недоступны.',
                ),
                'create',
              )
            }
          >
            {t('Create file backup', 'Создать файловую копию')}
          </button>
        </div>
        {!local && (
          <p className="note">
            {t(
              'Full filesystem backup requires a drive mounted on this server. Use Files and personal-data exports for Bridge connections.',
              'Полная файловая копия требует накопителя, смонтированного на сервере. Для Bridge используйте Файлы и экспорт личных данных.',
            )}
          </p>
        )}
        <ErrorMessage error={state.error ?? operation.error} />
        {state.data?.jobs
          .filter((j) => j.action.startsWith('phone.backup'))
          .slice(0, 4)
          .map((j) => (
            <div key={j.id}>
              <p>
                {j.command} · {j.status}
              </p>
              {j.status === 'running' && (
                <progress aria-label={t('Backup progress', 'Ход копирования')} />
              )}
              <JsonReport value={j.report ?? { output: j.output }} />
            </div>
          ))}
      </Card>
      <Card>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {[
                  t('Date', 'Дата'),
                  t('Name', 'Название'),
                  t('Files', 'Файлы'),
                  t('Size', 'Размер'),
                  t('State', 'Состояние'),
                  t('Actions', 'Действия'),
                ].map((v) => (
                  <th key={v}>{v}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {state.data?.backups.map((b) => (
                <tr key={text(b.id)}>
                  <td>{text(b.created)}</td>
                  <td>{text(b.label) || text(b.id)}</td>
                  <td>{text(b.files)}</td>
                  <td>{bytes(typeof b.bytes === 'number' ? b.bytes : null)}</td>
                  <td>
                    <span className="chip">
                      {text(b.state)} ·{' '}
                      {b.complete ? t('Complete', 'Полная') : t('Partial', 'Частичная')}
                    </span>
                    {b.manifest_ok === false && (
                      <span className="error-text">
                        {t('Manifest changed', 'Манифест изменён')}
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="form-row">
                      <button
                        className="btn ghost"
                        disabled={busy || b.state !== 'ready'}
                        onClick={() =>
                          operation.mutate({ action: 'phone.backup.verify', id: text(b.id) })
                        }
                      >
                        {t('Verify', 'Проверить')}
                      </button>
                      <button
                        className="btn ghost"
                        disabled={busy || b.state !== 'ready'}
                        onClick={() => {
                          setId(text(b.id));
                          setPlanJob(null);
                          setConsumed(false);
                        }}
                      >
                        {t('Restore…', 'Восстановить…')}
                      </button>
                      <button
                        className="btn ghost"
                        disabled={busy}
                        onClick={() =>
                          confirm.ask(
                            `${t('Delete server backup', 'Удалить копию с сервера')} ${text(b.id)}?`,
                            { delete: text(b.id) },
                          )
                        }
                      >
                        {t('Delete', 'Удалить')}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      {id && (
        <Card>
          <h2>
            {t('Restore preview', 'План восстановления')}: {id}
          </h2>
          <p className="note">
            {t(
              'Only new files are written. Existing files are never overwritten or deleted.',
              'Записываются только новые файлы. Существующие файлы не удаляются и не перезаписываются.',
            )}
          </p>
          <div className="form-row">
            <Field label={t('Only this folder (optional)', 'Только эта папка (необязательно)')}>
              <input value={only} onChange={(e) => setOnly(e.target.value)} />
            </Field>
            <button
              className="btn secondary"
              disabled={!device || !local || busy || operation.isPending}
              onClick={() => {
                setConsumed(false);
                setPlanJob(null);
                operation.mutate(
                  { action: 'phone.backup.restore', id, device, ...(only ? { only } : {}) },
                  { onSuccess: (r) => setPlanJob({ id: r.id, key }) },
                );
              }}
            >
              {t('Show plan', 'Показать план')}
            </button>
            <button
              className="btn primary"
              disabled={!plan || !plan.new || busy || consumed}
              onClick={() =>
                confirm.ask(
                  `${t('Write new files', 'Записать новые файлы')}: ${plan?.new ?? 0}?`,
                  'apply',
                )
              }
            >
              {t('Restore new files', 'Восстановить новые файлы')}
            </button>
            <button
              className="btn ghost"
              onClick={() => {
                setId('');
                setPlanJob(null);
              }}
            >
              {t('Close', 'Закрыть')}
            </button>
          </div>
          {plan && <JsonReport value={plan} />}
        </Card>
      )}
      <SettingsBackup device={device} />
      {confirm.dialog(async (action) => {
        if (typeof action === 'object') {
          await api.request(
            '/api/backups',
            { action: 'delete', id: action.delete, confirm: true },
            objectSchema,
          );
          if (id === action.delete) {
            setId('');
            setPlanJob(null);
          }
        } else if (action === 'create')
          await operation.mutateAsync({ action: 'phone.backup.create', device });
        else {
          if (!plan || consumed) throw Error('Preview expired');
          setConsumed(true);
          setPlanJob(null);
          await operation.mutateAsync({
            action: 'phone.backup.restore',
            id,
            device,
            ...(only ? { only } : {}),
            apply: true,
            confirm: true,
          });
        }
        await cache.invalidateQueries({ queryKey: ['workspace'] });
      })}
    </>
  );
}
