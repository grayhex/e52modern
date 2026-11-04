import { Download, Network, ShieldCheck } from 'lucide-react';
import { useWorkspace } from '../hooks/useWorkspace';
import { usePreferences } from '../state/app';
import { packageLink } from '../utils/packages';
import { Card, ErrorMessage } from '../components/ui';
import { bytes } from '../utils/files';

/** Locally built or published packages, with the next steps for each one. */
export default function Packages() {
  const { t } = usePreferences();
  const workspace = useWorkspace();
  const built = workspace.data?.packages ?? [];
  const library = workspace.data?.library ?? [];
  return (
    <>
      <h1>{t('Installation packages', 'Установочные пакеты')}</h1>
      <ErrorMessage error={workspace.error} />
      <Card>
        <h2>{t('Built packages', 'Собранные пакеты')}</h2>
        <p className="note">
          {t(
            'SIS/SISX files made by SymPort. A package here is not installed on any phone.',
            'SIS/SISX, собранные в SymPort. Пакет из этого списка не установлен ни на одном телефоне.',
          )}
        </p>
        <PackageTable items={built} source="build" />
      </Card>
      <Card>
        <h2>{t('Published theme library', 'Опубликованная библиотека тем')}</h2>
        <PackageTable items={library} source="library" />
      </Card>
      <p className="note">
        {t('To send a package to the phone use ', 'Чтобы передать пакет на телефон, откройте ')}
        <a href="#apps/installed">{t('My applications', 'Мои приложения')}</a>
        {t('; to build a kit with its runtimes use ', '; чтобы собрать комплект с runtime — ')}
        <a href="#apps/kits">{t('Application kits', 'Комплекты приложений')}</a>.
      </p>
    </>
  );
}

function PackageTable({
  items,
  source,
}: {
  items: { id: string; name: string; kind?: string | undefined; size?: number | undefined }[];
  source: 'build' | 'library';
}) {
  const { t } = usePreferences();
  if (!items.length) return <p className="empty">{t('Nothing here yet.', 'Пока пусто.')}</p>;
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>{t('Name', 'Имя')}</th>
            <th>{t('Kind', 'Тип')}</th>
            <th>{t('Size', 'Размер')}</th>
            <th>{t('Actions', 'Действия')}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.name}</td>
              <td>{item.kind ?? '—'}</td>
              <td>{item.size === undefined ? '—' : bytes(item.size)}</td>
              <td className="row-actions">
                {source === 'build' && (
                  <a
                    className="btn ghost"
                    href={`/api/download?id=${encodeURIComponent(item.id)}`}
                    download={item.name}
                  >
                    <Download size={14} aria-hidden="true" /> {t('Download', 'Скачать')}
                  </a>
                )}
                <a
                  className="btn ghost"
                  href={packageLink('tools/certificates', source, item.id, item.kind ?? 'app')}
                >
                  <ShieldCheck size={14} aria-hidden="true" /> {t('Certificates', 'Сертификаты')}
                </a>
                <a
                  className="btn ghost"
                  href={packageLink('apps/dependencies', source, item.id, item.kind ?? 'app')}
                >
                  <Network size={14} aria-hidden="true" /> {t('Dependencies', 'Зависимости')}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
