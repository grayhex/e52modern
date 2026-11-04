import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi, usePreferences } from '../state/app';
import { keys, useDevices } from '../api/queries';
import { Card, DeviceSelect, ErrorMessage, ConfirmDialog, supports } from '../components/ui';
import type { FileEntry } from '../api/contracts';
type Pending = {
  action: 'delete' | 'mkdir' | 'upload' | 'transfer';
  path: string;
  content?: string;
};
function join(path: string, name: string) {
  return [path.replace(/\/$/, ''), name].filter(Boolean).join('/');
}
async function encode(file: File) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let result = '';
  for (const byte of bytes) result += String.fromCharCode(byte);
  return btoa(result);
}
function save(content: string, name: string) {
  const bytes = Uint8Array.from(atob(content), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes]));
  const link = Object.assign(document.createElement('a'), { href: url, download: name });
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export default function Files() {
  const api = useApi();
  const queryClient = useQueryClient();
  const { t } = usePreferences();
  const devices = useDevices();
  const [device, setDevice] = useState('');
  const [path, setPath] = useState('');
  const [draftPath, setDraftPath] = useState('');
  const [directory, setDirectory] = useState('');
  const [upload, setUpload] = useState<File | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [view, setView] = useState<'table' | 'grid'>('table');
  const [message, setMessage] = useState('');
  const selected = devices.data?.devices.find((d) => d.id === device);
  const listing = useQuery({
    queryKey: keys.files(device, path),
    queryFn: ({ signal }) => api.list(device, path, signal),
    enabled: !!device,
    retry: false,
  });
  const mutate = useMutation({
    mutationFn: (op: Pending) => api.fileAction(op.action, device, op.path, op.content),
    onSuccess: async (result) => {
      setPending(null);
      setMessage([result.status, result.destination].filter(Boolean).join(' · '));
      await queryClient.invalidateQueries({ queryKey: ['files', device] });
    },
  });
  const download = useMutation({
    mutationFn: (entry: FileEntry) => api.download(device, join(path, entry.name)),
    onSuccess: (result) => save(result.content, result.name),
  });
  function choose(id: string) {
    setDevice(id);
    setPath('');
    setDraftPath('');
    setPending(null);
    setMessage('');
  }
  async function stage(action: 'upload' | 'transfer') {
    if (!upload) return;
    if (upload.size > (action === 'transfer' ? 32 : 8) * 1024 ** 2) {
      setMessage(t('File exceeds transfer limit', 'Файл превышает лимит передачи'));
      return;
    }
    setPending({ action, path: join(path, upload.name), content: await encode(upload) });
  }
  return (
    <>
      <h1>{t('Files', 'Файлы')}</h1>
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
          <label className="grow">
            {t('Path', 'Путь')}
            <input value={draftPath} onChange={(event) => setDraftPath(event.target.value)} />
          </label>
          <button className="btn secondary" disabled={!device} onClick={() => setPath(draftPath)}>
            {t('Open', 'Открыть')}
          </button>
        </div>
        <div className="form-row">
          <button
            className="btn ghost"
            onClick={() => {
              const parent = path.split('/').slice(0, -1).join('/');
              setPath(parent);
              setDraftPath(parent);
            }}
            disabled={!path}
          >
            ↑
          </button>
          <button
            className="btn ghost"
            aria-pressed={view === 'table'}
            onClick={() => setView('table')}
          >
            {t('Table', 'Таблица')}
          </button>
          <button
            className="btn ghost"
            aria-pressed={view === 'grid'}
            onClick={() => setView('grid')}
          >
            {t('Grid', 'Сетка')}
          </button>
        </div>
        <ErrorMessage error={listing.error ?? devices.error ?? download.error} />
        {listing.isFetching && <p role="status">{t('Reading…', 'Чтение…')}</p>}
        <div className={view === 'grid' ? 'react-file-grid' : 'table-scroll'}>
          {listing.data?.entries.map((entry) => (
            <article className="react-file" key={entry.name}>
              <button
                className="btn ghost"
                onClick={() => {
                  if (entry.directory) {
                    const next = join(path, entry.name);
                    setPath(next);
                    setDraftPath(next);
                  } else download.mutate(entry);
                }}
              >
                {entry.directory ? '▸' : '↓'} {entry.name}
              </button>
              <span>{entry.size == null ? '' : `${entry.size} B`}</span>
              <button
                className="btn ghost"
                disabled={!supports(selected, 'delete')}
                onClick={() => setPending({ action: 'delete', path: join(path, entry.name) })}
              >
                {t('Delete', 'Удалить')}
              </button>
            </article>
          ))}
        </div>
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
        <div className="form-row">
          <label>
            {t('New folder', 'Новая папка')}
            <input value={directory} onChange={(event) => setDirectory(event.target.value)} />
          </label>
          <button
            className="btn secondary"
            disabled={!directory || !supports(selected, 'mkdir')}
            onClick={() => setPending({ action: 'mkdir', path: join(path, directory) })}
          >
            {t('Create', 'Создать')}
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
