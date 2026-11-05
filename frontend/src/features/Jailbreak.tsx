import { encode } from '../utils/files';
import { PageHeader } from '../components/kit';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { useDevices } from '../api/queries';
import { fileSchema, jsonSchema, objectSchema, payload, text } from '../api/workspace';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
import { Download, Field, JsonReport } from '../components/workspace';
const runSchema = z
  .object({
    id: z.string(),
    method: z.string(),
    created: z.string(),
    identity: objectSchema,
    rollback_scope: z.string(),
    blocking_reasons: z.array(z.string()),
    manual_steps: z.array(z.string()),
    rollback_manual: z.array(z.string()),
    staged: z.array(objectSchema),
  })
  .catchall(jsonSchema);
const archiveSchema = z.object({
  id: z.string(),
  name: z.string(),
  sha256: z.string(),
  entries: z.array(objectSchema),
});
const stateSchema = z.object({
  archives: z.array(archiveSchema),
  runs: z.array(runSchema),
  reason: z.string(),
});
export default function Jailbreak() {
  const api = useApi(),
    { t, device, setDevice } = usePreferences(),
    devices = useDevices(),
    cache = useQueryClient();
  const [archive, setArchive] = useState(''),
    [file, setFile] = useState<File | null>(null),
    [selected, setSelected] = useState<Set<string>>(new Set()),
    [method, setMethod] = useState('norton'),
    [identity, setIdentity] = useState<Record<string, string>>({
      model: '',
      rm: '',
      firmware: '',
      symbian: '9.3',
    }),
    [settings, setSettings] = useState(''),
    [run, setRun] = useState<z.infer<typeof runSchema> | null>(null),
    [path, setPath] = useState(''),
    [step, setStep] = useState('install'),
    [result, setResult] = useState('not-tested'),
    [rollback, setRollback] = useState<z.infer<typeof objectSchema> | null>(null),
    [download, setDownload] = useState<z.infer<typeof fileSchema> | null>(null);
  const confirm = useConfirmedAction<string>();
  const state = useQuery({
    queryKey: ['jailbreak'],
    queryFn: ({ signal }) =>
      api.request('/api/jailbreak', { action: 'state' }, stateSchema, signal),
  });
  const operation = useMutation({
    mutationFn: async (fn: () => Promise<void>) => fn(),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ['jailbreak'] });
    },
  });
  const entries = state.data?.archives.find((a) => a.id === archive)?.entries ?? [];
  return (
    <>
      <PageHeader
        title={t('Jailbreak Manager (experimental)', 'Jailbreak Manager (экспериментальный)')}
      />
      <p className="disclaimer">
        {t(
          'System automation is blocked. File transfer does not install or apply patches. Rollback removes only unchanged files staged by this workflow; system changes require manual recovery.',
          'Системная автоматизация заблокирована. Передача файлов не устанавливает и не применяет патчи. Откат удаляет только неизменённые файлы этого процесса; системные изменения требуют ручного восстановления.',
        )}
      </p>
      <ErrorMessage error={state.error ?? operation.error} />
      <Card>
        <h2>1 / {t('Review your archive', 'Проверка архива')}</h2>
        <div className="form-row">
          <Field label="ZIP · 16 MiB">
            <input
              type="file"
              accept=".zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </Field>
          <button
            className="btn secondary"
            disabled={!file || operation.isPending}
            onClick={() =>
              operation.mutate(async () => {
                if (!file || file.size > 16 * 1024 ** 2) throw Error('ZIP limit: 16 MiB');
                const r = await api.request(
                  '/api/jailbreak',
                  { action: 'import', name: file.name, content: await encode(file) },
                  archiveSchema,
                );
                setArchive(r.id);
                setSelected(new Set());
              })
            }
          >
            {t('Inspect archive', 'Проверить архив')}
          </button>
          <Field label={t('Imported archive', 'Загруженный архив')}>
            <select
              value={archive}
              onChange={(e) => {
                setArchive(e.target.value);
                setSelected(new Set());
              }}
            >
              <option value="">—</option>
              {state.data?.archives.map((a) => (
                <option value={a.id} key={a.id}>
                  {a.name} · {a.sha256.slice(0, 12)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="scroll-y">
          {entries.map((f, i) => {
            const analysis = objectSchema.catch({}).parse(f.analysis),
              blocked =
                !!f.excluded ||
                analysis.signature === 'invalid' ||
                f.e52 === 'incompatible-target-claim' ||
                !['sis', 'patch', 'binary'].includes(text(f.kind));
            return (
              <label className="lab-upload-entry" key={i}>
                <input
                  type="checkbox"
                  checked={selected.has(text(f.sha256))}
                  disabled={blocked}
                  onChange={(e) =>
                    setSelected((current) => {
                      const next = new Set(current);
                      if (e.target.checked) next.add(text(f.sha256));
                      else next.delete(text(f.sha256));
                      return next;
                    })
                  }
                />
                <span>
                  {text(f.name)} · {text(f.excluded) || text(f.e52)} · {text(analysis.signature)} ·{' '}
                  {text(f.sha256).slice(0, 12)}
                </span>
              </label>
            );
          })}
        </div>
        <p className="note">
          {t(
            'Keys are excluded. Files are inspected, never executed by SymPort. A hash identifies a file; it does not establish safety.',
            'Ключи исключаются. SymPort анализирует файлы и не запускает их. Хеш определяет файл, но не доказывает безопасность.',
          )}
        </p>
      </Card>
      <Card>
        <h2>2 / {t('Identify and plan', 'Устройство и план')}</h2>
        <div className="form-row">
          <DeviceSelect value={device} onChange={setDevice} />
          <button
            className="btn secondary"
            disabled={!device}
            onClick={() => {
              const d = devices.data?.devices.find((d) => d.id === device);
              if (d)
                setIdentity({
                  model: d.model ?? '',
                  rm: d.rm ?? '',
                  firmware: d.firmware ?? '',
                  symbian: d.model_profile?.symbian ?? '9.3',
                });
            }}
          >
            {t('Use available identity', 'Использовать доступные сведения')}
          </button>
          <Field label={t('Method', 'Метод')}>
            <select value={method} onChange={(e) => setMethod(e.target.value)}>
              <option value="norton">Symantec / Norton</option>
              <option value="umu">UMU Nokia</option>
              <option value="rompatcher">ROMPatcher+ / InstallServer FP2</option>
            </select>
          </Field>
        </div>
        <div className="react-fields">
          {Object.entries(identity).map(([k, v]) => (
            <Field key={k} label={k}>
              <input
                value={v}
                onChange={(e) => setIdentity({ ...identity, [k]: e.target.value })}
              />
            </Field>
          ))}
        </div>
        <Field
          label={t(
            'Record clock, installer settings and existing patches',
            'Запишите время, настройки установщика и существующие патчи',
          )}
        >
          <textarea
            maxLength={2000}
            value={settings}
            onChange={(e) => setSettings(e.target.value)}
          />
        </Field>
        <button
          className="btn primary"
          disabled={!archive || !device || operation.isPending}
          onClick={() =>
            operation.mutate(async () => {
              setRollback(null);
              setRun(
                await api.request(
                  '/api/jailbreak',
                  payload({
                    action: 'plan',
                    method,
                    archive,
                    device,
                    ...identity,
                    settings,
                    files: [...selected],
                  }),
                  runSchema,
                ),
              );
            })
          }
        >
          {t('Create dry-run plan', 'Создать план без записи')}
        </button>
      </Card>
      {run && (
        <Card>
          <h2>3 / {t('Controlled workflow', 'Контролируемый процесс')}</h2>
          <p className="note">{run.rollback_scope}</p>
          {run.blocking_reasons.map((r) => (
            <p className="error-text" key={r}>
              {r}
            </p>
          ))}
          {run.staged.map((f, i) => (
            <p key={i}>
              {text(f.name)} → {text(f.path)} · {text(f.state)}
            </p>
          ))}
          <Field label={t('Accessible backup folder', 'Доступная папка для копирования')}>
            <input value={path} onChange={(e) => setPath(e.target.value)} />
          </Field>
          <div className="form-row">
            {[
              ['backup', 'Back up accessible data', 'Скопировать доступные данные'],
              ['stage', 'Transfer to isolated folder', 'Передать в изолированную папку'],
            ].map(([action, en, ru]) => (
              <button
                className="btn secondary"
                key={action}
                disabled={confirm.busy}
                onClick={() =>
                  confirm.ask(
                    action === 'stage'
                      ? t(
                          'Stage unverified files? This only copies files; it does not install or apply patches.',
                          'Передать непроверенные файлы? Это только копирование, без установки и применения патчей.',
                        )
                      : t(
                          'Back up accessible regular files? This is a partial backup, not system recovery.',
                          'Скопировать доступные обычные файлы? Это частичная копия, не восстановление системы.',
                        ),
                    action ?? '',
                  )
                }
              >
                {t(en ?? '', ru ?? '')}
              </button>
            ))}
            <button
              className="btn ghost"
              onClick={() =>
                operation.mutate(async () =>
                  setDownload(
                    await api.request(
                      '/api/jailbreak',
                      { action: 'backup-export', id: run.id },
                      fileSchema,
                    ),
                  ),
                )
              }
            >
              {t('Download backup ZIP', 'Скачать ZIP копии')}
            </button>
          </div>
          <p className="note">
            {t(
              'Backup is limited to 8 MiB / 500 regular files; it does not include ROM, internal system memory, settings or installed apps.',
              'Копия ограничена 8 МиБ / 500 обычными файлами; она не включает ROM, системную память, настройки или установленные приложения.',
            )}
          </p>
          <h2>4 / {t('Phone steps', 'Действия на телефоне')}</h2>
          <ol>
            {run.manual_steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          <div className="form-row">
            <Field label={t('Manual action', 'Ручное действие')}>
              <select value={step} onChange={(e) => setStep(e.target.value)}>
                {[
                  'install',
                  'quarantine-restore',
                  'apply-patch',
                  'disable-patch',
                  'uninstall',
                  'restore-settings',
                  'probe-install',
                ].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </Field>
            <Field label={t('Observed result', 'Наблюдаемый результат')}>
              <select value={result} onChange={(e) => setResult(e.target.value)}>
                {['not-tested', 'pass', 'fail'].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </Field>
            <button
              className="btn secondary"
              onClick={() =>
                confirm.ask(
                  `${t('Confirm this manual phone action separately', 'Отдельно подтвердите ручное действие на телефоне')}: ${step} → ${result}?`,
                  'manual-step',
                )
              }
            >
              {t('Record phone action', 'Зафиксировать действие')}
            </button>
            <button
              className="btn ghost"
              onClick={() =>
                operation.mutate(async () =>
                  setDownload(
                    await api.request(
                      '/api/jailbreak',
                      { action: 'probe', id: run.id },
                      fileSchema,
                    ),
                  ),
                )
              }
            >
              {t('Download safe test SIS', 'Скачать безопасный тестовый SIS')}
            </button>
          </div>
          <p className="note">
            {t(
              'The probe contains a text file only. Its installation does not prove a jailbreak or AllFiles access.',
              'Тестовый пакет содержит только текстовый файл. Его установка не доказывает разблокировку или доступ AllFiles.',
            )}
          </p>
          <h2>5 / Rollback</h2>
          <ol>
            {run.rollback_manual.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          <div className="form-row">
            <button
              className="btn secondary"
              onClick={() =>
                operation.mutate(async () =>
                  setRollback(
                    await api.request(
                      '/api/jailbreak',
                      { action: 'rollback-plan', id: run.id },
                      objectSchema,
                    ),
                  ),
                )
              }
            >
              {t('Preview rollback', 'План отката')}
            </button>
            <button
              className="btn destructive"
              disabled={!rollback || confirm.busy}
              onClick={() =>
                confirm.ask(
                  t(
                    'Remove only unchanged files created by this workflow? System changes cannot be rolled back automatically.',
                    'Удалить только неизменённые файлы этого процесса? Системные изменения автоматически не откатываются.',
                  ),
                  'rollback',
                )
              }
            >
              {t('Remove staged files', 'Удалить переданные файлы')}
            </button>
          </div>
          {rollback && <JsonReport value={rollback} />}
          <JsonReport value={run} />
          <Download
            content={btoa(unescape(encodeURIComponent(JSON.stringify(run, null, 2))))}
            name="symport-experimental-workflow.json"
            mime="application/json"
          />
        </Card>
      )}
      {download && (
        <Card>
          <Download {...download} />
        </Card>
      )}
      <Card>
        <h2>{t('Workflow history', 'История процессов')}</h2>
        {state.data?.runs.map((r) => (
          <button
            className="btn ghost"
            key={r.id}
            onClick={() => {
              setRun(r);
              setRollback(null);
            }}
          >
            {text(r.identity.model)} · {r.method} · {r.created}
          </button>
        ))}
        <p>
          <a
            className="text-link"
            href="https://lpcwiki.miraheze.org/wiki/Jailbreaking_S60_devices?oldid=71013"
            target="_blank"
            rel="noreferrer"
          >
            {t('Source guide', 'Исходное руководство')} ↗
          </a>
        </p>
      </Card>
      {confirm.dialog(async (action) => {
        if (!run) return;
        setRollback(null);
        const extra =
          action === 'stage'
            ? { ack_risk: true }
            : action === 'manual-step'
              ? { step, result, confirm_system: true }
              : action === 'backup'
                ? { path }
                : {};
        setRun(
          await api.request(
            '/api/jailbreak',
            payload({ action, id: run.id, confirm: true, ...extra }),
            runSchema,
          ),
        );
        await cache.invalidateQueries({ queryKey: ['jailbreak'] });
      })}
    </>
  );
}
