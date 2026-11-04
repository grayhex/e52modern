import { encode } from '../utils/files';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useApi, usePreferences } from '../state/app';
import { useDevices } from '../api/queries';
import { objectSchema } from '../api/workspace';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
import { Field } from '../components/workspace';
export default function Transfer({ kind }: { kind: 'software' | 'media' }) {
  const api = useApi(),
    { t, device, setDevice } = usePreferences(),
    devices = useDevices(),
    phone = devices.data?.devices.find((d) => d.id === device),
    opp = phone?.capabilities.includes('opp-push');
  const [files, setFiles] = useState<File[]>([]),
    [path, setPath] = useState(''),
    [mediaKind, setMediaKind] = useState('audio'),
    [completed, setCompleted] = useState(0);
  const confirm = useConfirmedAction<File[]>();
  const validate = useMutation({
    mutationFn: async () => {
      const limit = (kind === 'media' ? 64 : 32) * 1024 ** 2;
      if (files.some((f) => !f.size || f.size > limit))
        throw Error(t('File exceeds transfer limit', 'Файл превышает лимит передачи'));
      confirm.ask(
        t(
          'Transfer selected files? Complete installation or choose your ringtone on the phone.',
          'Передать выбранные файлы? Завершите установку или назначьте мелодию на телефоне.',
        ) + `\n${device}\n${files.map((f) => f.name).join(' · ')}`,
        files,
      );
    },
  });
  return (
    <Card>
      <h2>
        {kind === 'media'
          ? t('Upload music / video', 'Загрузить музыку / видео')
          : t('Transfer apps / games', 'Передать программы / игры')}
      </h2>
      <div className="form-row">
        <DeviceSelect value={device} onChange={setDevice} capability="transfer" />
        <Field label={t('Destination folder', 'Папка назначения')}>
          <input
            disabled={!!opp}
            value={opp ? '' : path}
            onChange={(e) => setPath(e.target.value)}
          />
        </Field>
        {kind === 'media' && (
          <select
            aria-label={t('Media kind', 'Вид медиа')}
            value={mediaKind}
            onChange={(e) => setMediaKind(e.target.value)}
          >
            <option value="audio">{t('Music', 'Музыка')}</option>
            <option value="video">{t('Video', 'Видео')}</option>
          </select>
        )}
      </div>
      <label
        className="upload-zone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          setFiles([...e.dataTransfer.files]);
        }}
      >
        {t('Choose files or drop them here', 'Выберите файлы или перетащите сюда')}
        <input
          type="file"
          multiple
          accept={kind === 'software' ? '.sis,.sisx,.jar,.jad' : undefined}
          onChange={(e) => setFiles([...(e.target.files ?? [])])}
        />
      </label>
      <p>{files.map((f) => f.name).join(' · ')}</p>
      <button
        className="btn primary"
        disabled={
          !device || !phone?.capabilities.includes('transfer') || !files.length || confirm.busy
        }
        onClick={() => validate.mutate()}
      >
        {t('Transfer', 'Передать')}
      </button>
      <ErrorMessage error={validate.error ?? confirm.error} />
      <p role="status">
        {completed} / {files.length} · {t('transferred; not installed', 'передано; не установлено')}
      </p>
      {confirm.dialog(async (batch) => {
        setCompleted(0);
        for (const [index, file] of batch.entries()) {
          await api.request(
            '/api/manager',
            {
              action: kind === 'media' ? 'media-upload' : 'software-transfer',
              device,
              path: opp ? '' : [path.replace(/\/$/, ''), file.name].filter(Boolean).join('/'),
              content: await encode(file),
              ...(kind === 'media' ? { kind: mediaKind } : {}),
              confirm: true,
            },
            objectSchema,
          );
          setCompleted(index + 1);
        }
      })}
    </Card>
  );
}
