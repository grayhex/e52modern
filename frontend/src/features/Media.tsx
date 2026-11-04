import { bytes } from '../utils/files';
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { useDevices } from '../api/queries';
import { mediaSchema, payload, type MediaItem } from '../api/workspace';
import { Card, CapabilityHint, DeviceSelect, ErrorMessage } from '../components/ui';
import { Field, Modal } from '../components/workspace';
import Transfer from './Transfer';
const url = (device: string, item: MediaItem, download = false) =>
  '/api/media/file?' +
  new URLSearchParams({
    device,
    path: item.path,
    revision: item.revision,
    ...(download ? { download: '1' } : {}),
  }).toString();
export default function Media() {
  const { device, setDevice, t } = usePreferences();
  return (
    <>
      <h1>{t('Media Gallery', 'Медиагалерея')}</h1>
      <Card>
        <DeviceSelect value={device} onChange={setDevice} />
      </Card>
      <Gallery key={device} device={device} />
      <Transfer kind="media" />
    </>
  );
}
function Gallery({ device }: { device: string }) {
  const api = useApi(),
    { t } = usePreferences();
  const devices = useDevices(),
    canRead = devices.data?.devices
      .find((d) => d.id === device)
      ?.capabilities.includes('media-read');
  const galleryDevice = devices.data?.devices.find((d) => d.id === device);
  const [draft, setDraft] = useState(''),
    [path, setPath] = useState<string | null>(null),
    [search, setSearch] = useState(''),
    [kind, setKind] = useState(''),
    [sort, setSort] = useState('newest'),
    [page, setPage] = useState(1),
    [selected, setSelected] = useState<Set<string>>(new Set()),
    [preview, setPreview] = useState<MediaItem | null>(null);
  const listing = useQuery({
    queryKey: ['media', device, path],
    queryFn: ({ signal }) =>
      api.request(
        '/api/manager',
        { action: 'media-list', device, path: path ?? '' },
        mediaSchema,
        signal,
      ),
    enabled: !!device && !!canRead && path !== null,
  });
  const items = (listing.data?.items ?? [])
    .filter(
      (i) =>
        (!kind || i.kind === kind) &&
        i.path.toLocaleLowerCase().includes(search.toLocaleLowerCase()),
    )
    .sort((a, b) =>
      sort === 'name'
        ? a.path.localeCompare(b.path)
        : sort === 'size'
          ? b.size - a.size
          : b.modified - a.modified,
    )
    .slice(0, page * 48);
  const thumbs = useQuery({
    queryKey: [
      'media-thumbnails',
      device,
      path,
      items.filter((i) => i.kind === 'photo').map((i) => i.revision),
    ],
    enabled: items.length > 0,
    queryFn: async ({ signal }) => {
      const result: Record<string, { url: string; dimensions: string; reason: string }> = {};
      const photos = items.filter((i) => i.kind === 'photo');
      let next = 0;
      async function worker() {
        while (next < photos.length && !signal.aborted) {
          const item = photos[next++];
          if (!item) continue;
          try {
            const r = await api.request(
              '/api/manager',
              { action: 'media-thumbnail', device, path: item.path, revision: item.revision },
              z.object({
                status: z.string(),
                content: z.string().optional(),
                width: z.number().optional(),
                height: z.number().optional(),
                reason: z.string().optional(),
              }),
              signal,
            );
            result[item.path] = {
              url: r.content ? 'data:image/jpeg;base64,' + r.content : '',
              dimensions: r.width && r.height ? `${r.width}×${r.height}` : '',
              reason: r.reason ?? '',
            };
          } catch {
            if (signal.aborted) throw signal.reason;
          }
        }
      }
      await Promise.all(Array.from({ length: 4 }, worker));
      return result;
    },
    staleTime: 300000,
  });
  const zip = useMutation({
    mutationFn: () =>
      api.request(
        '/api/media/export',
        payload({
          device,
          items: (listing.data?.items ?? [])
            .filter((i) => selected.has(i.path))
            .map(({ path, revision }) => ({ path, revision })),
        }),
        z.object({ url: z.string() }),
      ),
  });
  return (
    <>
      <Card>
        <div className="form-row">
          <Field label={t('Folder', 'Папка')}>
            <input value={draft} onChange={(e) => setDraft(e.target.value)} />
          </Field>
          <button
            className="btn primary"
            disabled={!device || !canRead || listing.isFetching}
            onClick={() => {
              if (path === draft) void listing.refetch();
              setPath(draft);
              setSelected(new Set());
              setPage(1);
            }}
          >
            {t('Read gallery', 'Открыть галерею')}
          </button>
          <Field label={t('Search', 'Поиск')}>
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </Field>
          <select
            aria-label={t('Media type', 'Тип медиа')}
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setPage(1);
            }}
          >
            {[
              ['', 'All', 'Все'],
              ['photo', 'Photos', 'Фото'],
              ['video', 'Videos', 'Видео'],
              ['audio', 'Music', 'Музыка'],
            ].map(([v, en, ru]) => (
              <option value={v} key={v}>
                {t(en ?? '', ru ?? '')}
              </option>
            ))}
          </select>
          <select
            aria-label={t('Sort', 'Сортировка')}
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="newest">{t('Newest', 'Новые')}</option>
            <option value="name">{t('Name', 'Название')}</option>
            <option value="size">{t('Size', 'Размер')}</option>
          </select>
        </div>
        {!canRead && (
          <p className="note">
            {t(
              'Gallery is unavailable through this connection. Use Files to download exposed files.',
              'Галерея недоступна через это подключение. Откройте «Файлы» для скачивания доступных файлов.',
            )}
          </p>
        )}
        {!canRead && <CapabilityHint device={galleryDevice} ops={['media.read']} />}
        <ErrorMessage error={listing.error ?? zip.error} />
        {listing.data?.truncated && (
          <p className="note">
            {t(
              'Search limit reached. Select a narrower folder.',
              'Достигнут лимит поиска. Выберите более узкую папку.',
            )}
          </p>
        )}
        {!!listing.data?.skipped && (
          <p className="note">
            {t('Some folders are inaccessible.', 'Некоторые папки недоступны.')}
          </p>
        )}
        <div className="form-row">
          <button
            className="btn ghost"
            onClick={() => setSelected(new Set(items.map((i) => i.path)))}
          >
            {t('Select visible', 'Выбрать видимые')}
          </button>
          <button className="btn ghost" onClick={() => setSelected(new Set())}>
            {t('Clear selection', 'Снять выбор')}
          </button>
          <button
            className="btn secondary"
            disabled={!selected.size || zip.isPending}
            onClick={() => zip.mutate()}
          >
            {t('Prepare ZIP', 'Подготовить ZIP')} ({selected.size})
          </button>
          {zip.data && (
            <a className="btn secondary" href={zip.data.url} download="symport-media.zip">
              {t('Download ZIP', 'Скачать ZIP')}
            </a>
          )}
        </div>
        <div className="media-grid">
          {items.map((item) => (
            <article
              className={`media-item ${selected.has(item.path) ? 'selected' : ''}`}
              key={item.path}
            >
              <input
                type="checkbox"
                aria-label={`${t('Select', 'Выбрать')} ${item.name}`}
                checked={selected.has(item.path)}
                onChange={(e) =>
                  setSelected((current) => {
                    const next = new Set(current);
                    if (e.target.checked) next.add(item.path);
                    else next.delete(item.path);
                    return next;
                  })
                }
              />
              <button className="media-open" onClick={() => setPreview(item)}>
                {thumbs.data?.[item.path]?.url ? (
                  <img
                    className="media-art"
                    loading="lazy"
                    src={thumbs.data[item.path]?.url}
                    alt=""
                  />
                ) : item.kind === 'video' ? (
                  <VideoThumbnail source={url(device, item)} />
                ) : (
                  <span className="media-art" title={thumbs.data?.[item.path]?.reason}>
                    {item.kind === 'audio' ? '♫' : '▧'}
                  </span>
                )}
                <span className="media-copy">
                  {item.name}
                  <small>
                    {bytes(item.size)} · {new Date(item.modified * 1000).toLocaleDateString()} ·{' '}
                    {thumbs.data?.[item.path]?.dimensions}
                  </small>
                </span>
              </button>
              {item.kind !== 'photo' && (
                <a
                  className="btn ghost"
                  href={
                    '#personalize/ringtones?' +
                    new URLSearchParams({ device, path: item.path, revision: item.revision })
                  }
                >
                  {t('Create ringtone', 'Создать рингтон')}
                </a>
              )}
            </article>
          ))}
        </div>
        <button
          className="btn ghost"
          disabled={items.length < page * 48}
          onClick={() => setPage(page + 1)}
        >
          {t('Show more', 'Показать ещё')}
        </button>
      </Card>
      {preview && <MediaPreview device={device} item={preview} onClose={() => setPreview(null)} />}
    </>
  );
}

function VideoThumbnail({ source }: { source: string }) {
  const ref = useRef<HTMLVideoElement>(null),
    [visible, setVisible] = useState(false),
    [failed, setFailed] = useState(false),
    { t } = usePreferences();
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '100px' },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return failed ? (
    <span
      className="media-art"
      title={t(
        'Video thumbnail unavailable; download the original.',
        'Миниатюра видео недоступна; скачайте оригинал.',
      )}
    >
      ▷
    </span>
  ) : (
    <video
      className="media-art"
      ref={ref}
      muted
      playsInline
      aria-hidden="true"
      preload={visible ? 'metadata' : 'none'}
      src={visible ? source : undefined}
      onLoadedMetadata={(e) => {
        const video = e.currentTarget;
        if (Number.isFinite(video.duration) && video.duration > 0)
          video.currentTime = Math.min(0.1, video.duration / 2);
      }}
      onError={() => setFailed(true)}
    />
  );
}
function MediaPreview({
  device,
  item,
  onClose,
}: {
  device: string;
  item: MediaItem;
  onClose: () => void;
}) {
  const { t } = usePreferences(),
    [metadata, setMetadata] = useState('');
  const loaded = (media: HTMLMediaElement) => {
    const duration = Number.isFinite(media.duration) ? `${media.duration.toFixed(1)} s` : '';
    const dimensions =
      media instanceof HTMLVideoElement ? `${media.videoWidth}×${media.videoHeight}` : '';
    setMetadata([duration, dimensions].filter(Boolean).join(' · '));
  };
  return (
    <Modal title={item.name} onClose={onClose}>
      <div className="gallery-player">
        {item.kind === 'photo' ? (
          <img src={url(device, item)} alt={item.name} />
        ) : item.kind === 'audio' ? (
          <audio
            controls
            preload="metadata"
            src={url(device, item)}
            onLoadedMetadata={(e) => loaded(e.currentTarget)}
          />
        ) : (
          <video
            controls
            preload="metadata"
            src={url(device, item)}
            onLoadedMetadata={(e) => loaded(e.currentTarget)}
          />
        )}
      </div>
      <p>
        {item.path} · {bytes(item.size)} · {item.mime} ·{' '}
        {new Date(item.modified * 1000).toLocaleString()} · {metadata}
      </p>
      <a className="text-link" href={url(device, item, true)} download={item.name}>
        {t('Download original', 'Скачать оригинал')}
      </a>
    </Modal>
  );
}
