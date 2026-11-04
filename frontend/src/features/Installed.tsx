import { useMutation } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { objectSchema, text } from '../api/workspace';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
import Transfer from './Transfer';
export default function Installed() {
  const api = useApi(),
    { t, device, setDevice } = usePreferences();
  const scan = useMutation({
    mutationFn: () =>
      api.request(
        '/api/manager',
        { action: 'apps-inventory', device },
        z.object({
          packages: z.array(objectSchema),
          unreadable: z.array(z.json()),
          duplicates_by_uid: objectSchema,
        }),
      ),
  });
  return (
    <>
      <h1>{t('Apps & games', 'Программы и игры')}</h1>
      <Transfer kind="software" />
      <Card>
        <h2>{t('Package inventory', 'Пакеты на телефоне')}</h2>
        <div className="form-row">
          <DeviceSelect value={device} onChange={setDevice} capability="files" />
          <button
            className="btn secondary"
            disabled={!device || scan.isPending}
            onClick={() => scan.mutate()}
          >
            {t('Scan packages', 'Найти пакеты')}
          </button>
        </div>
        <p className="note">
          {t(
            'This lists package files. It does not confirm which applications are installed.',
            'Это список файлов пакетов. Он не подтверждает, какие приложения установлены.',
          )}
        </p>
        <ErrorMessage error={scan.error} />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {['Path', 'Name', 'UID', 'Version', 'Signature', 'CRC'].map((k) => (
                  <th key={k}>
                    {t(
                      k,
                      {
                        Path: 'Путь',
                        Name: 'Имя',
                        UID: 'UID',
                        Version: 'Версия',
                        Signature: 'Подпись',
                        CRC: 'CRC',
                      }[k] ?? k,
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {scan.data?.packages.map((p, i) => (
                <tr key={i}>
                  <td>{text(p.path)}</td>
                  <td>{text(p.name)}</td>
                  <td>{text(p.uid)}</td>
                  <td>{text(p.version)}</td>
                  <td>{p.signed ? t('Signed', 'Подписан') : t('Unsigned', 'Не подписан')}</td>
                  <td>{p.checksums_ok ? '✓' : '✕'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {scan.data && (
          <p>
            {scan.data.packages.length} · {t('Unreadable', 'Нечитаемых')}:{' '}
            {scan.data.unreadable.length} · {t('Duplicate UIDs', 'Повторы UID')}:{' '}
            {Object.keys(scan.data.duplicates_by_uid).length}
          </p>
        )}
      </Card>
    </>
  );
}
