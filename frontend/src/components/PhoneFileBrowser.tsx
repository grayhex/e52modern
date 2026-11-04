import { useMemo } from 'react';
import { FileBrowser, FileBrowserProvider } from '@harryy/react-file-browser';
import { useApi, usePreferences } from '../state/app';
import { createPhoneAdapter, toDevicePath, type PhoneFileCapabilities } from '../api/phoneFiles';
import { packageLink } from '../utils/packages';

/** The phone's files in react-file-browser; `path` is the browser path ("/" = the connection's root). */
export default function PhoneFileBrowser({
  device,
  label,
  capabilities,
  path,
  onPath,
}: {
  device: string;
  label: string;
  capabilities: PhoneFileCapabilities;
  path: string;
  onPath: (path: string) => void;
}) {
  const api = useApi();
  const { t } = usePreferences();
  const adapter = useMemo(
    () => createPhoneAdapter(api, device, capabilities),
    [api, device, capabilities.upload, capabilities.mkdir, capabilities.delete], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const writable = capabilities.upload || capabilities.mkdir || capabilities.delete;
  return (
    <div className="phone-files">
      {/* storage:null keeps file names out of localStorage; transfers live in memory only. */}
      <FileBrowserProvider options={{ storage: null, maxConcurrentUploads: 2 }}>
        <FileBrowser
          key={device}
          adapter={adapter}
          rootLabel={label}
          path={path || '/'}
          onPathChange={(next) => onPath(next)}
          density="compact"
          readOnly={!writable}
          editors={[]}
          uploadConflictResolutions={['keep-both', 'skip']}
          uploadPolicy={{ maxFileSizeBytes: 8 * 1024 ** 2 }}
          emptyState={{
            title: t('This folder is empty', 'Эта папка пуста'),
            description: t(
              'Nothing was reported by the connection.',
              'Подключение ничего не вернуло.',
            ),
          }}
          renderItemMeta={(item) =>
            item.kind === 'file' && /\.sisx?$/i.test(item.name) ? (
              <a
                className="underline"
                href={`${packageLink('tools/certificates', 'device', '')}&${new URLSearchParams({ device, path: toDevicePath(item.path) })}`}
                onClick={(event) => event.stopPropagation()}
              >
                {t('Inspect package', 'Проверить пакет')}
              </a>
            ) : null
          }
        />
      </FileBrowserProvider>
    </div>
  );
}
