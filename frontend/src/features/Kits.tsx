import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { encode } from '../utils/files';
import { initialChoice } from '../utils/packages';
import { useApi, usePreferences } from '../state/app';
import { bundleSchema } from '../api/deps';
import { catalogSchema } from '../api/catalog';
import { payload } from '../api/workspace';
import { Card, ErrorMessage } from '../components/ui';
import { PackagePicker } from '../components/PackagePicker';
import { RuntimeFiles, TargetFields } from '../components/RuntimeInputs';
import { defaultTarget } from '../components/targets';
import { Download } from '../components/workspace';
import { StatusBadge } from '../components/DependencyReport';

/** Application kits: catalog sets plus a kit builder that orders an app with the runtimes you supply. */
export default function Kits() {
  const api = useApi();
  const { t } = usePreferences();
  const [choice, setChoice] = useState(initialChoice);
  const [target, setTarget] = useState(defaultTarget);
  const [firmwareId, setFirmwareId] = useState('');
  const [runtimes, setRuntimes] = useState<File[]>([]);
  const [incomplete, setIncomplete] = useState(false);
  const catalog = useQuery({
    queryKey: ['catalog'],
    queryFn: ({ signal }) => api.request('/api/catalog', { action: 'list' }, catalogSchema, signal),
  });
  const build = useMutation({
    mutationFn: async () => {
      const body = payload({
        action: 'bundle',
        source: choice.source,
        reference: choice.reference,
        kind: choice.kind,
        target,
        allow_incomplete: incomplete,
      });
      if (choice.source === 'upload') {
        if (!choice.file || choice.file.size > 32 * 1024 ** 2)
          throw Error(t('Choose SIS/SISX up to 32 MiB', 'Выберите SIS/SISX до 32 МиБ'));
        body.name = choice.file.name;
        body.content = await encode(choice.file);
      }
      if (firmwareId) body.firmware_id = firmwareId;
      body.runtimes = await Promise.all(
        runtimes.map(async (file) => ({
          source: 'upload',
          name: file.name,
          content: await encode(file),
        })),
      );
      return api.request('/api/inspector', body, bundleSchema);
    },
  });
  const sets = Object.entries(catalog.data?.sets ?? {});
  const kit = build.data;
  return (
    <>
      <h1>{t('Application kits', 'Комплекты приложений')}</h1>
      <Card>
        <h2>{t('Kit with required runtimes', 'Комплект с необходимыми runtime')}</h2>
        <p className="note">
          {t(
            'Puts an application and the runtime packages YOU supply into a ZIP in the correct install order. SymPort never downloads a runtime by itself and cannot prove that the phone accepts the packages.',
            'Собирает приложение и предоставленные ВАМИ runtime-пакеты в ZIP в правильном порядке установки. SymPort сам не скачивает runtime и не может доказать, что телефон примет пакеты.',
          )}
        </p>
        <PackagePicker value={choice} onChange={setChoice} />
        <TargetFields
          target={target}
          onTarget={setTarget}
          firmwareId={firmwareId}
          onFirmware={setFirmwareId}
        />
        <RuntimeFiles files={runtimes} onFiles={setRuntimes} />
        <label className="settings-switch">
          <input
            type="checkbox"
            checked={incomplete}
            onChange={(e) => setIncomplete(e.target.checked)}
          />
          {t(
            'Also pack an INCOMPLETE kit (unresolved dependencies stay listed)',
            'Собрать и НЕПОЛНЫЙ комплект (нерешённые зависимости останутся в списке)',
          )}
        </label>
        <button className="btn primary" disabled={build.isPending} onClick={() => build.mutate()}>
          {t('Build kit', 'Собрать комплект')}
        </button>
        <ErrorMessage error={build.error} />
      </Card>
      {kit && (
        <Card>
          <h2>
            {t('Kit', 'Комплект')}{' '}
            <span
              className={`status-chip status-chip--${kit.status === 'complete' ? 'ok' : 'warn'}`}
            >
              {kit.status === 'complete' ? t('Complete', 'Полный') : t('Incomplete', 'Неполный')}
            </span>
          </h2>
          <ol className="kit-order">
            {kit.order.map((entry) => (
              <li key={entry.file}>
                <strong>{entry.name}</strong> {entry.version} ·{' '}
                {entry.role === 'application' ? t('application', 'приложение') : 'runtime'} ·{' '}
                <span className="lab-value">{entry.file}</span> · {entry.uid} ·{' '}
                {Math.ceil(entry.size / 1024)} KiB
                <br />
                <small className="lab-value">SHA-256 {entry.sha256}</small>
              </li>
            ))}
          </ol>
          {kit.unresolved.length > 0 && (
            <div className="note">
              <strong>{t('Unresolved (not in the kit)', 'Не решено (нет в комплекте)')}</strong>
              <ul>
                {kit.unresolved.map((u) => (
                  <li key={`${u.name}-${u.status}`}>
                    {u.name} {u.min_version ? `≥ ${u.min_version}` : ''}{' '}
                    <StatusBadge status={u.status} />
                  </li>
                ))}
              </ul>
            </div>
          )}
          {kit.unused_runtimes.length > 0 && (
            <p className="note">
              {t('Supplied but not required by anything: ', 'Предоставлены, но никому не нужны: ')}
              {kit.unused_runtimes.join(', ')}
            </p>
          )}
          <ul>
            {kit.instructions.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {kit.zip && kit.zip_name ? (
            <Download content={kit.zip} name={kit.zip_name} mime="application/zip" />
          ) : (
            <p className="note">
              {t(
                'No ZIP was made: add the missing runtime packages or allow an incomplete kit.',
                'ZIP не создан: добавьте недостающие runtime-пакеты или разрешите неполный комплект.',
              )}
            </p>
          )}
          <p className="note">
            {t(
              'The kit is a file bundle. Installing it is done on the phone, in the listed order.',
              'Комплект — набор файлов. Установка выполняется на телефоне в указанном порядке.',
            )}
          </p>
        </Card>
      )}
      <Card>
        <h2>{t('Catalog sets', 'Наборы каталога')}</h2>
        <p className="note">
          {t(
            'Saved lists of catalog applications; edit them in the ',
            'Сохранённые списки приложений каталога; изменяйте их в ',
          )}
          <a href="#apps/catalog">{t('App catalog', 'каталоге приложений')}</a>.
        </p>
        {sets.length === 0 ? (
          <p className="empty">{t('No saved sets yet.', 'Сохранённых наборов пока нет.')}</p>
        ) : (
          <ul>
            {sets.map(([name, ids]) => (
              <li key={name}>
                <strong>{name}</strong> — {ids.join(', ')}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
