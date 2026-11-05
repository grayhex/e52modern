import { deviceProfiles, profileLabel } from '../components/deviceProfiles';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronRight, File as FileIcon, Folder, Search, Trash2, Upload } from 'lucide-react';
import { useApi, usePreferences } from '../state/app';
import {
  childrenSchema,
  compareSchema,
  depsSchema,
  fileSchema,
  imageSchema,
  profileSchema,
  searchSchema,
  statusSchema,
  type FirmwareEntry,
} from '../api/firmware';
import { objectSchema } from '../api/workspace';
import { firmwareKeys, useFirmwareImages } from '../hooks/useFirmwareImages';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { bytes } from '../utils/files';
import { Card, ErrorMessage } from '../components/ui';
import { Download, Field } from '../components/workspace';

const KINDS = [
  'e32-exe',
  'e32-dll',
  'rom-image-exe',
  'rom-image-dll',
  'mbm',
  'mif',
  'resource',
  'sis',
  'plugin',
  'text',
  'image',
  'audio',
  'font',
  'data',
  'other',
];
const CAPS = [
  'NetworkServices',
  'LocalServices',
  'ReadUserData',
  'WriteUserData',
  'Location',
  'UserEnvironment',
  'AllFiles',
  'TCB',
  'CommDD',
  'DRM',
  'ProtServ',
  'SwEvent',
  'ReadDeviceData',
  'WriteDeviceData',
];

/** Firmware & ROM Explorer: static browser for firmware contents the user uploads. */
export default function Firmware() {
  const api = useApi();
  const { t } = usePreferences();
  const cache = useQueryClient();
  const images = useFirmwareImages();
  const [choice, setSelected] = useState('');
  const [name, setName] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const confirm = useConfirmedAction<string>();
  const ready = (images.data?.images ?? []).filter((i) => i.status === 'ready');
  const selected = ready.some((i) => i.id === choice) ? choice : (ready[0]?.id ?? '');
  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw Error(t('Choose a file', 'Выберите файл'));
      setProgress(0);
      const query = new URLSearchParams({ name: file.name, label: name });
      return api.uploadProgress(`/api/firmware/upload?${query}`, file, imageSchema, setProgress);
    },
    onSuccess: async (image) => {
      setFile(null);
      setSelected(image.id);
      await cache.invalidateQueries({ queryKey: firmwareKeys.images });
    },
  });
  return (
    <>
      <h1>Firmware &amp; ROM Explorer</h1>
      <Card>
        <p className="note">
          {t(
            'Browse firmware YOU supply: a ZIP of an unpacked Z: tree, or a raw core ROM image (experimental reader). Nothing is executed, flashed or redistributed; files stay on this server until you delete them. Nokia FPSX/VPL containers and ROFS images must be unpacked with a dedicated tool first.',
            'Просмотр прошивки, которую ВЫ загружаете: ZIP с распакованным деревом Z: или «сырой» образ core ROM (экспериментальный разбор). Ничего не запускается, не прошивается и не распространяется; файлы лежат на этом сервере до удаления. Контейнеры Nokia FPSX/VPL и образы ROFS сначала распакуйте отдельным инструментом.',
          )}
        </p>
        <div className="form-row">
          <Field label={t('ZIP or ROM image', 'ZIP или образ ROM')}>
            <input
              type="file"
              accept=".zip,.rom,.bin,.img"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </Field>
          <Field label={t('Label (optional)', 'Название (необязательно)')}>
            <input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
          </Field>
          <button
            className="btn primary"
            disabled={!file || upload.isPending}
            onClick={() => upload.mutate()}
          >
            <Upload size={16} aria-hidden="true" />{' '}
            {t('Upload and index', 'Загрузить и проиндексировать')}
          </button>
        </div>
        {upload.isPending && (
          <progress value={progress} max={100} aria-label={t('Upload progress', 'Ход загрузки')} />
        )}
        <ErrorMessage error={upload.error ?? images.error} />
        <ImageList
          images={images.data?.images ?? []}
          selected={selected}
          onSelect={setSelected}
          onDelete={(id) =>
            confirm.ask(
              t(
                'Delete this firmware image from the server?',
                'Удалить этот образ прошивки с сервера?',
              ),
              id,
            )
          }
        />
      </Card>
      {selected && (
        <Explorer
          id={selected}
          images={ready.map((i) => ({ id: i.id, name: i.label || i.name }))}
        />
      )}
      {confirm.dialog(async (id) => {
        await api.request('/api/firmware', { action: 'delete', id, confirm: true }, objectSchema);
        await cache.invalidateQueries({ queryKey: firmwareKeys.images });
      })}
    </>
  );
}

function ImageList({
  images,
  selected,
  onSelect,
  onDelete,
}: {
  images: {
    id: string;
    name: string;
    label?: string | undefined;
    size: number;
    kind: string;
    status: string;
    progress: { done: number; total: number };
    error?: string | null | undefined;
    files?: number | null | undefined;
  }[];
  selected: string;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const { t } = usePreferences();
  if (!images.length)
    return <p className="empty">{t('No firmware uploaded yet.', 'Прошивки ещё не загружены.')}</p>;
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>{t('Image', 'Образ')}</th>
            <th>{t('Type', 'Тип')}</th>
            <th>{t('Size', 'Размер')}</th>
            <th>{t('Files', 'Файлов')}</th>
            <th>{t('State', 'Состояние')}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {images.map((image) => (
            <tr key={image.id} aria-selected={image.id === selected}>
              <td>
                <button
                  className="btn ghost"
                  disabled={image.status !== 'ready'}
                  aria-pressed={image.id === selected}
                  onClick={() => onSelect(image.id)}
                >
                  {image.label || image.name}
                </button>
              </td>
              <td>{image.kind === 'zip' ? 'ZIP' : 'ROM'}</td>
              <td>{bytes(image.size)}</td>
              <td>{image.files ?? '—'}</td>
              <td>
                {image.status === 'indexing'
                  ? `${t('Indexing', 'Индексация')} ${image.progress.done}/${image.progress.total || '?'}`
                  : image.status === 'failed'
                    ? `${t('Failed', 'Ошибка')}: ${image.error ?? ''}`
                    : t('Ready', 'Готов')}
              </td>
              <td>
                <button
                  className="btn ghost"
                  aria-label={`${t('Delete', 'Удалить')} ${image.name}`}
                  onClick={() => onDelete(image.id)}
                >
                  <Trash2 size={14} aria-hidden="true" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Explorer({ id, images }: { id: string; images: { id: string; name: string }[] }) {
  const api = useApi();
  const { t } = usePreferences();
  const [dir, setDir] = useState('Z:');
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState('');
  const [capability, setCapability] = useState('');
  const [uid, setUid] = useState('');
  const [path, setPath] = useState('');
  const searching = !!(query || kind || capability || uid);
  const status = useQuery({
    queryKey: ['firmware', id, 'status'],
    queryFn: ({ signal }) =>
      api.request('/api/firmware', { action: 'status', id }, statusSchema, signal),
  });
  const children = useQuery({
    queryKey: ['firmware', id, 'children', dir],
    queryFn: ({ signal }) =>
      api.request('/api/firmware', { action: 'children', id, dir }, childrenSchema, signal),
    enabled: !searching,
  });
  const search = useQuery({
    queryKey: ['firmware', id, 'search', query, kind, capability, uid],
    queryFn: ({ signal }) =>
      api.request(
        '/api/firmware',
        { action: 'search', id, query, kind, capability, uid, limit: 200 },
        searchSchema,
        signal,
      ),
    enabled: searching,
  });
  const entries: FirmwareEntry[] = searching
    ? (search.data?.entries ?? [])
    : (children.data?.files ?? []);
  const crumbs = dir.split('/');
  return (
    <>
      <Card>
        <h2>{t('Contents', 'Содержимое')}</h2>
        {status.data?.counts && (
          <p>
            {status.data.counts.files} {t('files', 'файлов')} · {bytes(status.data.counts.bytes)} ·{' '}
            {status.data.counts.e32} E32 ·{' '}
            {Object.entries(status.data.counts.by_kind)
              .map(([k, v]) => `${k}: ${v}`)
              .join(' · ')}
            {status.data.skipped_count
              ? ` · ${t('skipped', 'пропущено')}: ${status.data.skipped_count}`
              : ''}
          </p>
        )}
        <div className="form-row">
          <Field label={t('Search path', 'Поиск по пути')}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="avkon, .rsc, bin/…"
            />
          </Field>
          <Field label={t('Type', 'Тип')}>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="">{t('Any', 'Любой')}</option>
              {KINDS.map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
          </Field>
          <Field label={t('Capability', 'Capability')}>
            <select value={capability} onChange={(e) => setCapability(e.target.value)}>
              <option value="">{t('Any', 'Любая')}</option>
              {CAPS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </Field>
          <Field label="UID / SID">
            <input value={uid} onChange={(e) => setUid(e.target.value)} placeholder="0x100039ce" />
          </Field>
        </div>
        {!searching && (
          <nav className="fw-crumbs" aria-label="Z:">
            {crumbs.map((part, i) => {
              const target = crumbs.slice(0, i + 1).join('/');
              return (
                <span key={target}>
                  {i > 0 && <ChevronRight size={12} aria-hidden="true" />}
                  <button className="btn ghost" onClick={() => setDir(target)}>
                    {part}
                  </button>
                </span>
              );
            })}
          </nav>
        )}
        <ErrorMessage error={children.error ?? search.error ?? status.error} />
        <div className="fw-browser">
          {!searching && (
            <ul className="fw-folders" aria-label={t('Folders', 'Папки')}>
              {children.data?.folders.map((folder) => (
                <li key={folder.path}>
                  <button className="btn ghost" onClick={() => setDir(folder.path)}>
                    <Folder size={14} aria-hidden="true" /> {folder.name}{' '}
                    <small>({folder.files})</small>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="table-scroll fw-files">
            {searching && search.data && (
              <p role="status">
                {search.data.total} {t('matches', 'совпадений')}
                {search.data.total > search.data.entries.length
                  ? ` · ${t('first', 'первые')} ${search.data.entries.length}`
                  : ''}
              </p>
            )}
            <table>
              <thead>
                <tr>
                  <th>{t('Name', 'Имя')}</th>
                  <th>{t('Type', 'Тип')}</th>
                  <th>{t('Size', 'Размер')}</th>
                  <th>UID</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.path} aria-selected={entry.path === path}>
                    <td>
                      <button className="btn ghost" onClick={() => setPath(entry.path)}>
                        <FileIcon size={14} aria-hidden="true" />{' '}
                        {searching ? entry.path.slice(3) : entry.name}
                      </button>
                    </td>
                    <td>
                      {entry.kind}
                      {entry.basis === 'extension' && (
                        <small title={t('guessed from the extension', 'определено по расширению')}>
                          {' '}
                          *
                        </small>
                      )}
                    </td>
                    <td>{bytes(entry.size)}</td>
                    <td className="lab-value">{entry.uids?.[2] ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!entries.length && (
              <p className="empty">
                {searching ? <Search size={14} aria-hidden="true" /> : null}{' '}
                {t('Nothing here.', 'Здесь пусто.')}
              </p>
            )}
          </div>
        </div>
        <p className="note">
          *{' '}
          {t(
            'Type guessed from the file extension; other types come from file headers.',
            'Тип определён по расширению; остальные — по заголовкам файлов.',
          )}
        </p>
      </Card>
      {path && <FileDetails id={id} path={path} onOpen={setPath} />}
      <Compare current={id} images={images} />
      <Profile id={id} />
    </>
  );
}

function Row({ k, v }: { k: string; v: unknown }) {
  return (
    <div>
      <dt>{k}</dt>
      <dd className="lab-value">{v === null || v === undefined || v === '' ? '—' : String(v)}</dd>
    </div>
  );
}

function FileDetails({
  id,
  path,
  onOpen,
}: {
  id: string;
  path: string;
  onOpen: (path: string) => void;
}) {
  const api = useApi();
  const { t } = usePreferences();
  const file = useQuery({
    queryKey: ['firmware', id, 'file', path],
    queryFn: ({ signal }) =>
      api.request('/api/firmware', { action: 'file', id, path }, fileSchema, signal),
  });
  const deps = useQuery({
    queryKey: ['firmware', id, 'deps', path],
    queryFn: ({ signal }) =>
      api.request('/api/firmware', { action: 'dependencies', id, path }, depsSchema, signal),
  });
  const entry = file.data?.entry;
  const e32 = entry?.e32 as Record<string, unknown> | undefined;
  return (
    <Card>
      <h2>{entry?.name ?? path}</h2>
      <ErrorMessage error={file.error ?? deps.error} />
      {entry && (
        <dl className="device-details">
          <Row k={t('Path', 'Путь')} v={entry.path} />
          <Row k={t('Type', 'Тип')} v={`${entry.kind} (${entry.basis})`} />
          <Row k={t('Size', 'Размер')} v={`${bytes(entry.size)} (${entry.size} B)`} />
          <Row k="SHA-256" v={entry.sha256} />
          <Row k="UID1–3" v={entry.uids?.join(' ')} />
          {e32 && (
            <>
              <Row k={t('Kind', 'Вид')} v={e32.is_dll ? 'DLL' : 'EXE'} />
              <Row
                k="Secure ID / Vendor ID"
                v={`${String(e32.secure_id)} / ${String(e32.vendor_id)}`}
              />
              <Row k={t('Module version', 'Версия модуля')} v={e32.module_version} />
              <Row
                k={t('Kernel / CPU / ABI', 'Ядро / CPU / ABI')}
                v={`${String(e32.kernel)} / ${String(e32.cpu)} / ${String(e32.abi)}`}
              />
              <Row k={t('Compression', 'Сжатие')} v={e32.compression} />
              <Row
                k="Capabilities"
                v={
                  Array.isArray(e32.capabilities)
                    ? (e32.capabilities as string[]).join(', ')
                    : t('not in this header format', 'нет в этом формате заголовка')
                }
              />
              <Row k={t('Exports', 'Экспорты')} v={e32.export_count} />
              <Row
                k={t('Heap min/max · stack', 'Куча мин/макс · стек')}
                v={`${String(e32.heap_min)} / ${String(e32.heap_max)} · ${String(e32.stack_size)}`}
              />
            </>
          )}
          {entry.mbm && (
            <Row
              k="MBM"
              v={`${String(entry.mbm.count)} ${t('bitmaps', 'битмапов')}; ${(
                (entry.mbm.bitmaps as
                  { width: number; height: number; bits_per_pixel: number }[] | undefined) ?? []
              )
                .slice(0, 4)
                .map((b) => `${b.width}×${b.height}@${b.bits_per_pixel}`)
                .join(', ')}`}
            />
          )}
          {entry.mif && (
            <Row
              k="MIF"
              v={`${t('format version', 'версия формата')} ${String(entry.mif.format_version)}`}
            />
          )}
          {entry.parse_error && (
            <Row k={t('Parse note', 'Замечание разбора')} v={entry.parse_error} />
          )}
        </dl>
      )}
      <h3>{t('System dependencies', 'Системные зависимости')}</h3>
      {deps.data?.note && <p className="note">{deps.data.note}</p>}
      {deps.data?.imports && (
        <ul>
          {deps.data.imports.map((imp) => (
            <li key={imp.name}>
              {imp.resolved ? (
                <button className="btn ghost" onClick={() => onOpen(imp.resolved ?? path)}>
                  {imp.name}
                </button>
              ) : (
                imp.name
              )}{' '}
              <small>
                {imp.status === 'present-in-image'
                  ? t('present in this image', 'есть в образе')
                  : t('missing from this image', 'нет в образе')}
              </small>
            </li>
          ))}
        </ul>
      )}
      {!!deps.data?.imported_by.length && (
        <>
          <h3>{t('Imported by', 'Импортируют')}</h3>
          <ul>
            {deps.data.imported_by.slice(0, 40).map((p) => (
              <li key={p}>
                <button className="btn ghost" onClick={() => onOpen(p)}>
                  {p}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {file.data?.hex_head && (
        <details>
          <summary>{t('First 256 bytes', 'Первые 256 байт')}</summary>
          <pre className="hex">
            {(file.data.hex_head.match(/.{1,32}/g) ?? [])
              .map((row) => row.replace(/(..)/g, '$1 '))
              .join('\n')}
          </pre>
        </details>
      )}
      {file.data?.read_error && <p className="note">{file.data.read_error}</p>}
    </Card>
  );
}

function Compare({ current, images }: { current: string; images: { id: string; name: string }[] }) {
  const api = useApi();
  const { t } = usePreferences();
  const [other, setOther] = useState('');
  const compare = useMutation({
    mutationFn: () =>
      api.request(
        '/api/firmware',
        { action: 'compare', a: current, b: other, limit: 200 },
        compareSchema,
      ),
  });
  const result = compare.data;
  return (
    <Card>
      <h2>{t('Compare two firmwares', 'Сравнение двух прошивок')}</h2>
      <div className="form-row">
        <Field label={t('Compare the selected image with', 'Сравнить выбранный образ с')}>
          <select value={other} onChange={(e) => setOther(e.target.value)}>
            <option value="">{t('Choose an image', 'Выберите образ')}</option>
            {images
              .filter((i) => i.id !== current)
              .map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name}
                </option>
              ))}
          </select>
        </Field>
        <button
          className="btn secondary"
          disabled={!other || compare.isPending}
          onClick={() => compare.mutate()}
        >
          {t('Compare', 'Сравнить')}
        </button>
      </div>
      <ErrorMessage error={compare.error} />
      {result && (
        <>
          <p role="status">
            A: {result.a.name} ({result.a.files}) → B: {result.b.name} ({result.b.files}) ·{' '}
            {t('only in A', 'только в A')}: {result.summary.only_a} · {t('only in B', 'только в B')}
            : {result.summary.only_b} · {t('changed', 'изменено')}: {result.summary.changed} (
            {result.summary.e32_changed} E32) · {t('identical', 'совпадает')}:{' '}
            {result.summary.identical}
          </p>
          <p className="note">{result.basis}</p>
          <ListBlock
            title={t('Only in A', 'Только в A')}
            items={result.only_a}
            truncated={result.truncated.only_a}
          />
          <ListBlock
            title={t('Only in B', 'Только в B')}
            items={result.only_b}
            truncated={result.truncated.only_b}
          />
          <h3>{t('Changed', 'Изменено')}</h3>
          <ul>
            {result.changed.map((c) => (
              <li key={c.path}>
                <span className="lab-value">{c.path}</span>
                {Object.keys(c.details).length > 0 && <small> — {JSON.stringify(c.details)}</small>}
              </li>
            ))}
          </ul>
          {result.truncated.changed && (
            <p className="note">{t('List truncated.', 'Список обрезан.')}</p>
          )}
        </>
      )}
    </Card>
  );
}

function ListBlock({
  title,
  items,
  truncated,
}: {
  title: string;
  items: string[];
  truncated: boolean;
}) {
  const { t } = usePreferences();
  if (!items.length) return null;
  return (
    <details>
      <summary>
        {title} ({items.length}
        {truncated ? '+' : ''})
      </summary>
      <ul>
        {items.map((p) => (
          <li key={p} className="lab-value">
            {p}
          </li>
        ))}
      </ul>
      {truncated && <p className="note">{t('List truncated.', 'Список обрезан.')}</p>}
    </details>
  );
}

function Profile({ id }: { id: string }) {
  const api = useApi();
  const { t } = usePreferences();
  const [version, setVersion] = useState('');
  const [model, setModel] = useState('nokia-e52');
  const profile = useMutation({
    mutationFn: () =>
      api.request(
        '/api/firmware',
        { action: 'profile', id, firmware_version: version, profile: model },
        profileSchema,
      ),
  });
  return (
    <Card>
      <h2>
        {t(
          'Firmware profile for compatibility checks',
          'Профиль прошивки для проверок совместимости',
        )}
      </h2>
      <p className="note">
        {t(
          'Exports the DLL names of this image as a profile for Certificate Inspector. Export ordinals are unknown, so ordinal-level checks stay unknown. You can also pick the image directly in Dependencies & compatibility.',
          'Выгружает имена DLL образа как профиль для Certificate Inspector. Ординалы экспорта неизвестны, поэтому проверки на уровне ординалов остаются неизвестными. Образ можно выбрать и прямо в «Зависимостях и совместимости».',
        )}
      </p>
      <div className="form-row">
        <Field label={t('Declared device model', 'Модель устройства (укажите самостоятельно)')}>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {deviceProfiles.map((p) => (
              <option key={p.id} value={p.id}>
                {profileLabel(p)}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label={t('Exact firmware version of this image', 'Точная версия прошивки этого образа')}
        >
          <input value={version} onChange={(e) => setVersion(e.target.value)} maxLength={120} />
        </Field>
        <button
          className="btn secondary"
          disabled={!version.trim() || profile.isPending}
          onClick={() => profile.mutate()}
        >
          {t('Build profile', 'Собрать профиль')}
        </button>
      </div>
      <ErrorMessage error={profile.error} />
      {profile.data && (
        <Download
          content={btoa(unescape(encodeURIComponent(JSON.stringify(profile.data, null, 2))))}
          name="firmware-profile.json"
          mime="application/json"
        />
      )}
    </Card>
  );
}
