import { encode as encodeBlob } from '../utils/files';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi, usePreferences } from '../state/app';
import { useDevices } from '../api/queries';
import { Card, DeviceSelect, ErrorMessage, ConfirmDialog, supports } from '../components/ui';
import PhoneFileBrowser from '../components/PhoneFileBrowser';
import { Download, Field, JsonReport } from '../components/workspace';
import { fileSchema, objectSchema, payload } from '../api/workspace';
import { z } from 'zod';

type Pending = {
  action: 'upload' | 'transfer';
  path: string;
  content?: string;
};
function join(path: string, name: string) {
  return [path.replace(/\/$/, ''), name].filter(Boolean).join('/');
}
export default function Files() {
  const api = useApi();
  const queryClient = useQueryClient();
  const { t, device, setDevice } = usePreferences();
  const devices = useDevices();
  const [path, setPath] = useState('');
  const [upload, setUpload] = useState<File | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [message, setMessage] = useState('');
  const selected = devices.data?.devices.find((d) => d.id === device);
  const mutate = useMutation({
    mutationFn: (op: Pending) => api.fileAction(op.action, device, op.path, op.content),
    onSuccess: async (result) => {
      setPending(null);
      setMessage([result.status, result.destination].filter(Boolean).join(' · '));
      await queryClient.invalidateQueries({ queryKey: ['files', device] });
    },
  });
  function choose(id: string) {
    setDevice(id);
    setPath('');
    setPending(null);
    setMessage('');
  }
  async function stage(action: 'upload' | 'transfer') {
    if (!upload) return;
    if (upload.size > (action === 'transfer' ? 32 : 8) * 1024 ** 2) {
      setMessage(t('File exceeds transfer limit', 'Файл превышает лимит передачи'));
      return;
    }
    setPending({ action, path: join(path, upload.name), content: await encodeBlob(upload) });
  }
  const rootPath = path ? '/' + path : '/';
  const label = selected?.name ?? selected?.model ?? device;
  return (
    <>
      <h1>{t('File manager', 'Файловый менеджер')}</h1>
      <Card>
        <div className="form-row">
          <DeviceSelect value={device} onChange={choose} capability="files" />
          <button
            className="btn secondary"
            disabled={devices.isFetching}
            onClick={() => {
              void devices.refetch();
            }}
          >
            {t('Find phone', 'Найти телефон')}
          </button>
        </div>
        {device && !supports(selected, 'list') && (
          <p className="note">
            {t(
              'This connection cannot browse files. Choose a file transport in Connection.',
              'Это подключение не открывает файлы. Выберите файловый транспорт в разделе «Подключение».',
            )}
          </p>
        )}
        <ErrorMessage error={devices.error} />
        {device && supports(selected, 'list') ? (
          <PhoneFileBrowser
            device={device}
            label={label}
            capabilities={{
              upload: supports(selected, 'upload'),
              mkdir: supports(selected, 'mkdir'),
              delete: supports(selected, 'delete'),
            }}
            path={rootPath}
            onPath={(next) => setPath(next.replace(/^\/+/, ''))}
          />
        ) : (
          !device && (
            <p className="empty">
              {t(
                'Choose a connection to browse its files.',
                'Выберите подключение, чтобы открыть его файлы.',
              )}
            </p>
          )
        )}
        <p className="note">
          {t(
            'The file browser labels are in English. Existing files are never overwritten, and uploads are limited to 8 MiB.',
            'Подписи файлового браузера — на английском. Существующие файлы не перезаписываются, загрузка ограничена 8 МиБ.',
          )}
        </p>
      </Card>
      <Card>
        <div className="form-row">
          <label>
            {t('File', 'Файл')}
            <input type="file" onChange={(event) => setUpload(event.target.files?.[0] ?? null)} />
          </label>
          <button
            className="btn secondary"
            disabled={!upload || !supports(selected, 'upload')}
            onClick={() => {
              void stage('upload');
            }}
          >
            {t('Transfer file', 'Передать файл')}
          </button>
          <button
            className="btn secondary"
            disabled={!upload || !supports(selected, 'transfer')}
            onClick={() => {
              void stage('transfer');
            }}
          >
            SIS / SISX
          </button>
        </div>
        <p role="status">{message}</p>
        <p className="note">
          {t(
            'Sending a package does not install it. Existing files are not overwritten.',
            'Передача пакета не устанавливает его. Существующие файлы не перезаписываются.',
          )}
        </p>
      </Card>
      {device && supports(selected, 'backup') && (
        <FolderBackup
          key={`${device}:${path}`}
          device={device}
          path={path}
          onRestored={() => queryClient.invalidateQueries({ queryKey: ['files', device] })}
        />
      )}
      {pending && (
        <ConfirmDialog
          message={`${pending.action}: ${device}/${pending.path}`}
          busy={mutate.isPending}
          error={mutate.error}
          onCancel={() => {
            setPending(null);
            mutate.reset();
          }}
          onConfirm={() => mutate.mutate(pending)}
        />
      )}
      <ErrorMessage error={mutate.error} />
    </>
  );
}

function FolderBackup({
  device,
  path,
  onRestored,
}: {
  device: string;
  path: string;
  onRestored: () => Promise<void>;
}) {
  const api = useApi(),
    { t } = usePreferences(),
    [file, setFile] = useState<File | null>(null),
    [output, setOutput] = useState<z.infer<typeof fileSchema> | null>(null),
    [restore, setRestore] = useState<{ content: string; preview_sha256: string } | null>(null),
    confirm = useConfirmedAction<{ content: string; preview_sha256: string }>();
  const backup = useMutation({
    mutationFn: () => api.request('/api/manager', { action: 'backup', device, path }, fileSchema),
    onSuccess: setOutput,
  });
  const preview = useMutation({
    mutationFn: async () => {
      setRestore(null);
      if (!file || file.size > 8 * 1024 ** 2) throw Error('ZIP limit: 8 MiB');
      const content = await encodeBlob(file);
      const result = await api.request(
        '/api/manager',
        { action: 'restore-preview', device, path, content },
        z.object({
          sha256: z.string(),
          changes: z.array(z.object({ conflict: z.boolean() }).catchall(z.json())),
        }),
      );
      if (result.changes.length && !result.changes.some((c) => c.conflict))
        setRestore({ content, preview_sha256: result.sha256 });
      return result;
    },
  });
  return (
    <Card>
      <h2>{t('Folder backup / restore', 'Копия и восстановление папки')}</h2>
      <p className="note">
        {t(
          'Only regular files in this folder; subfolders are excluded. ZIP up to 8 MiB / 500 files. Restore never overwrites existing files.',
          'Только обычные файлы этой папки, без вложенных каталогов. ZIP до 8 МиБ / 500 файлов. Восстановление не перезаписывает существующие файлы.',
        )}
      </p>
      <p>
        {device}/{path}
      </p>
      <div className="form-row">
        <button
          className="btn secondary"
          disabled={backup.isPending}
          onClick={() => backup.mutate()}
        >
          {t('Download folder ZIP', 'Скачать ZIP папки')}
        </button>
        <Field label={t('Restore ZIP (8 MiB)', 'ZIP для восстановления (8 МиБ)')}>
          <input
            type="file"
            accept=".zip"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setRestore(null);
              preview.reset();
            }}
          />
        </Field>
        <button
          className="btn secondary"
          disabled={!file || preview.isPending}
          onClick={() => preview.mutate()}
        >
          {t('Preview restore', 'План восстановления')}
        </button>
        <button
          className="btn primary"
          disabled={!restore || confirm.busy}
          onClick={() => {
            if (restore)
              confirm.ask(
                `${t('Restore displayed new files into', 'Восстановить показанные новые файлы в')} ${device}/${path}?`,
                restore,
              );
          }}
        >
          {t('Restore', 'Восстановить')}
        </button>
      </div>
      <ErrorMessage error={backup.error ?? preview.error} />
      {preview.data && <JsonReport value={preview.data.changes} />}{' '}
      {output && <Download {...output} auto />}
      {confirm.dialog(async (value) => {
        setRestore(null);
        await api.request(
          '/api/manager',
          payload({ action: 'restore', device, path, ...value, confirm: true }),
          objectSchema,
        );
        await onRestored();
      })}
    </Card>
  );
}
