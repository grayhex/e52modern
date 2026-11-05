import { useProfiles } from '../api/queries';
import { PageHeader } from '../components/kit';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi, usePreferences } from '../state/app';
import { themeStudioSchema, themeProjectSchema, type ThemeProject } from '../api/p1';
import { fileSchema, objectSchema, type jsonSchema } from '../api/workspace';
import { Card, ErrorMessage } from '../components/ui';
import { Field, Download, JsonReport } from '../components/workspace';
import { encode, bytes } from '../utils/files';
import { packageLink } from '../utils/packages';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
import type { z } from 'zod';
type Body = Record<string, z.infer<typeof jsonSchema>>;
export default function ThemeStudio() {
  const api = useApi(),
    cache = useQueryClient(),
    { t } = usePreferences(),
    [id, setId] = useState(''),
    [name, setName] = useState('My Nokia Theme'),
    [pickedProfile, setProfile] = useState(''),
    profiles = useProfiles(),
    profile = pickedProfile || profiles[0]?.value || '',
    [variant, setVariant] = useState('light');
  const state = useQuery({
    queryKey: ['theme-studio'],
    queryFn: ({ signal }) =>
      api.request('/api/theme-studio', { action: 'list' }, themeStudioSchema, signal),
  });
  const create = useMutation({
    mutationFn: async (file?: File) => {
      if (file && file.size > 8 * 1024 ** 2) throw Error(t('SIS limit: 8 MiB', 'Лимит SIS: 8 МиБ'));
      return api.request(
        '/api/theme-studio',
        {
          action: file ? 'import' : 'create',
          name,
          profile,
          variant,
          ...(file ? { filename: file.name, content: await encode(file) } : {}),
        },
        themeProjectSchema,
      );
    },
    onSuccess: async (project) => {
      await cache.invalidateQueries({ queryKey: ['theme-studio'] });
      setId(project.id);
    },
  });
  return (
    <>
      <PageHeader title={t('Advanced Theme Studio', 'Редактор тем')} />
      <Card>
        <div className="react-fields">
          <Field label={t('Project', 'Проект')}>
            <select value={id} onChange={(e) => setId(e.target.value)}>
              <option value="">{t('New project', 'Новый проект')}</option>
              {state.data?.projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.profile} · r{p.revision}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('New theme name (ASCII)', 'Название новой темы (ASCII)')}>
            <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label={t('Screen profile', 'Профиль экрана')}>
            <select value={profile} onChange={(e) => setProfile(e.target.value)}>
              {profiles.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('Starting palette', 'Начальная палитра')}>
            <select value={variant} onChange={(e) => setVariant(e.target.value)}>
              {Object.keys(state.data?.palettes ?? { light: {}, dark: {} }).map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>
        </div>
        <div className="form-row">
          <button
            className="btn primary"
            disabled={create.isPending || !name.trim()}
            onClick={() => create.mutate(undefined)}
          >
            {t('Create editable CLEAR theme', 'Создать редактируемую тему CLEAR')}
          </button>
          <Field label={t('Import SIS theme (8 MiB)', 'Импорт SIS-темы (8 МиБ)')}>
            <input
              type="file"
              accept=".sis,.sisx"
              disabled={create.isPending}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) create.mutate(f);
                e.target.value = '';
              }}
            />
          </Field>
        </div>
        <p className="note">
          {t(
            'Palette, wallpaper and app-UID icons are editable in CLEAR projects. Imported SKN colour tables and SVG-T icons stay intact; supported MBM bitmaps and whole resources can be replaced. System layout is controlled by S60 firmware.',
            'В проектах CLEAR редактируются палитра, обои и иконки по UID приложения. Таблицы цветов SKN и значки SVG-T импортированных тем сохраняются без изменений; поддерживаемые битмапы MBM и целые ресурсы можно заменять. Системную геометрию задаёт прошивка S60.',
          )}
        </p>
        <ErrorMessage error={state.error ?? create.error} />
      </Card>
      {id && <Editor key={id} id={id} onDelete={() => setId('')} />}
    </>
  );
}
function Editor({ id, onDelete }: { id: string; onDelete: () => void }) {
  const api = useApi(),
    cache = useQueryClient(),
    { t } = usePreferences(),
    [uid, setUid] = useState(''),
    [unsigned, setUnsigned] = useState(false),
    [palette, setPalette] = useState<Record<string, string> | null>(null);
  const state = useQuery({
    queryKey: ['theme-project', id],
    queryFn: ({ signal }) =>
      api.request('/api/theme-studio', { action: 'project', id }, themeProjectSchema, signal),
  });
  const project = state.data;
  const operation = useMutation({
    mutationFn: (body: Body) =>
      api.request(
        '/api/theme-studio',
        { id, revision: project?.revision ?? 0, ...body },
        themeProjectSchema,
      ),
    onSuccess: async (p, body) => {
      cache.setQueryData(['theme-project', id], p);
      if (body.action === 'save') setPalette(null);
      await cache.invalidateQueries({ queryKey: ['theme-studio'] });
      await cache.invalidateQueries({ queryKey: ['theme-asset', id] });
    },
  });
  const upload = useMutation({
    mutationFn: async ({
      file,
      action,
      resource,
      index,
    }: {
      file: File;
      action: string;
      resource?: string;
      index?: number;
    }) => {
      const limit = action === 'resource-replace' ? 8 : 4;
      if (file.size > limit * 1024 ** 2)
        throw Error(`${t('File limit', 'Лимит файла')}: ${limit} MiB`);
      return operation.mutateAsync({
        action,
        content: await encode(file),
        uid,
        ...(resource ? { resource } : {}),
        ...(index !== undefined ? { index } : {}),
      });
    },
  });
  const exported = useMutation({
    mutationFn: () => api.request('/api/theme-studio', { action: 'export', id }, fileSchema),
  });
  const confirm = useConfirmedAction<string>();
  if (!project)
    return (
      <Card>
        <ErrorMessage error={state.error} />
        <p>{t('Loading project…', 'Загрузка проекта…')}</p>
      </Card>
    );
  const colors = palette ?? project.palette,
    built = project.built_revision === project.revision && !!project.build,
    pending = operation.isPending || upload.isPending;
  return (
    <>
      <div className="p1-theme-layout">
        <Card>
          <div className="card-head">
            <h2>{project.name}</h2>
            <span className="chip">
              {project.profile} · r{project.revision}
            </span>
          </div>
          <PhonePreview project={project} palette={colors} />
        </Card>
        <Card>
          <h2>{t('Design assets', 'Ресурсы оформления')}</h2>
          {project.mode === 'clear' ? (
            <>
              <div className="p1-palette">
                {Object.entries(colors).map(([role, color]) => (
                  <Field key={role} label={role}>
                    <input
                      type="color"
                      disabled={pending}
                      value={color}
                      onChange={(e) => setPalette({ ...colors, [role]: e.target.value })}
                    />
                  </Field>
                ))}
              </div>
              <button
                className="btn primary"
                disabled={!palette || pending}
                onClick={() => operation.mutate({ action: 'save', palette: colors })}
              >
                {t('Save palette', 'Сохранить палитру')}
              </button>
              <div className="react-fields">
                <Field
                  label={t(
                    'Wallpaper (centre crop, 4 MiB)',
                    'Обои (кадрирование по центру, 4 МиБ)',
                  )}
                >
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    disabled={pending}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) upload.mutate({ file, action: 'wallpaper' });
                      e.target.value = '';
                    }}
                  />
                </Field>
                <Field label={t('Application UID (8 hex digits)', 'UID приложения (8 hex-цифр)')}>
                  <input
                    value={uid}
                    maxLength={8}
                    placeholder="100058ec"
                    onChange={(e) => setUid(e.target.value)}
                  />
                </Field>
                <Field
                  label={t('Application icon (48×48, alpha)', 'Значок приложения (48×48, альфа)')}
                >
                  <input
                    type="file"
                    accept="image/png,image/webp"
                    disabled={pending || !/^[a-f0-9]{8}$/i.test(uid)}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) upload.mutate({ file, action: 'icon' });
                      e.target.value = '';
                    }}
                  />
                </Field>
              </div>
              <p>
                {t('Custom application icons', 'Значки приложений')}:{' '}
                {Object.keys(project.icons).join(', ') || '—'}
              </p>
              <div className="form-row">
                {project.wallpaper && (
                  <button
                    className="btn ghost"
                    disabled={pending}
                    onClick={() => operation.mutate({ action: 'wallpaper-remove' })}
                  >
                    {t('Reset wallpaper', 'Сбросить обои')}
                  </button>
                )}
                {Object.keys(project.icons).map((iconUid) => (
                  <div className="p1-icon-asset" key={iconUid}>
                    <IconAsset project={project} uid={iconUid} />
                    <button
                      className="btn ghost"
                      disabled={pending}
                      onClick={() => operation.mutate({ action: 'icon-remove', uid: iconUid })}
                    >
                      {t('Remove', 'Удалить')} {iconUid}
                    </button>
                  </div>
                ))}
              </div>
              {project.contrast && (
                <details>
                  <summary>{t('Text contrast', 'Контраст текста')}</summary>
                  {project.contrast.map((r, i) => (
                    <p key={i}>
                      {String(r.foreground)} / {String(r.background)} · {Number(r.ratio).toFixed(2)}
                      :1
                    </p>
                  ))}
                </details>
              )}
            </>
          ) : (
            <p className="note">
              {t(
                'This is a compiled theme. Colour tables are opaque; no palette reconstruction is claimed. Inspect and replace resources below, or start an editable CLEAR project. The original uploaded SIS is preserved.',
                'Это скомпилированная тема. Таблицы цветов не декодируются; восстановление палитры не заявляется. Исследуйте и заменяйте ресурсы ниже или создайте проект CLEAR. Исходный загруженный SIS сохраняется.',
              )}
            </p>
          )}
          <ErrorMessage error={operation.error ?? upload.error} />
          <p role="status">{pending ? t('Processing…', 'Обработка…') : null}</p>
        </Card>
      </div>
      <Card>
        <h2>{t('MBM / MIF / SKN resources', 'Ресурсы MBM / MIF / SKN')}</h2>
        {!project.resources.length && (
          <p>
            {t(
              'Build the theme to inspect generated resources.',
              'Соберите тему для просмотра сгенерированных ресурсов.',
            )}
          </p>
        )}
        {project.mode === 'clear' && !!project.resources.length && !built && (
          <p className="note">
            {t(
              'Resources below belong to the previous build. Rebuild this revision to inspect your changes.',
              'Ресурсы ниже относятся к предыдущей сборке. Соберите текущую ревизию для просмотра изменений.',
            )}
          </p>
        )}
        {project.resources.map((resource) => (
          <ResourceEditor
            key={`${resource.id}-${resource.sha256}`}
            project={project}
            resource={resource}
            upload={(file, action, index) =>
              upload.mutate({
                file,
                action,
                resource: resource.id,
                ...(index !== undefined ? { index } : {}),
              })
            }
            pending={pending}
          />
        ))}
        {project.blockers.map((b) => (
          <p className="error-text" key={b}>
            {b}
          </p>
        ))}
      </Card>
      <Card>
        <h2>{t('Build & inspect', 'Сборка и проверка')}</h2>
        <p className="note">
          {t(
            'Output is an unsigned SIS with a development UID. Repacking retains the imported UID (updates an existing theme) and removes its original signature. Keep the original installer. Inspect certificates and dependencies, then test in Emulator Lab; the phone may require an appropriately signed package. Apply themes in Symbian Themes, not by launching a UID.',
            'Результат — неподписанный SIS с UID разработки. Пересборка сохраняет UID импортированной темы (обновляет существующую тему) и удаляет исходную подпись. Сохраните оригинальный установщик. Проверьте сертификаты и зависимости, затем испытайте в Emulator Lab; телефон может потребовать правильно подписанный пакет. Тема применяется в меню «Темы» Symbian, а не запуском UID.',
          )}
        </p>
        <label className="p1-consent">
          <input
            type="checkbox"
            checked={unsigned}
            onChange={(e) => setUnsigned(e.target.checked)}
          />
          {t(
            'I understand the unsigned package and signature changes',
            'Я понимаю ограничения неподписанного пакета и изменение подписи',
          )}
        </label>
        <div className="form-row">
          <button
            className="btn primary"
            disabled={pending || !unsigned || !!palette || !!project.blockers.length}
            onClick={() => {
              exported.reset();
              operation.mutate({ action: 'build', confirm_unsigned: true });
            }}
          >
            {t('Build & statically validate SIS', 'Собрать и статически проверить SIS')}
          </button>
          <button
            className="btn secondary"
            disabled={!built || exported.isPending}
            onClick={() => exported.mutate()}
          >
            {t('Export SIS', 'Экспорт SIS')}
          </button>
          {built && (
            <>
              <a
                className="btn secondary"
                href={packageLink(
                  'tools/certificates',
                  'theme-studio',
                  id,
                  'theme',
                  project.profile,
                )}
              >
                {t('Inspect & transfer to Nokia', 'Проверить и передать на Nokia')}
              </a>
              <a
                className="btn secondary"
                href={packageLink('dev/lab', 'theme-studio', id, 'theme', project.profile)}
              >
                {t('Test theme in emulator', 'Испытать тему в эмуляторе')}
              </a>
            </>
          )}
          <button
            className="btn ghost"
            onClick={() =>
              confirm.ask(
                t(
                  'Delete this project and its local resources?',
                  'Удалить проект и его локальные ресурсы?',
                ),
                id,
              )
            }
          >
            {t('Delete project', 'Удалить проект')}
          </button>
        </div>
        {project.build && (
          <p>
            {project.build.status} · {project.build.signature} · {bytes(project.build.size)}
            <br />
            <code className="p1-hash">SHA-256 {project.build.sha256}</code>
            {!built && (
              <strong> · {t('Changes require a rebuild', 'Изменения требуют пересборки')}</strong>
            )}
          </p>
        )}
        <ErrorMessage error={exported.error} />
        {exported.data && built && <Download {...exported.data} />}
        <JsonReport value={project} />
      </Card>
      {confirm.dialog(async () => {
        await api.request(
          '/api/theme-studio',
          { action: 'delete', id, confirm: true },
          objectSchema,
        );
        await cache.invalidateQueries({ queryKey: ['theme-studio'] });
        onDelete();
      })}
    </>
  );
}
function ResourceEditor({
  project,
  resource,
  upload,
  pending,
}: {
  project: ThemeProject;
  resource: ThemeProject['resources'][number];
  upload: (file: File, action: string, index?: number) => void;
  pending: boolean;
}) {
  const api = useApi(),
    { t } = usePreferences(),
    [index, setIndex] = useState(0);
  const download = useMutation({
    mutationFn: () =>
      api.request(
        '/api/theme-studio',
        { action: 'asset', id: project.id, resource: resource.id },
        fileSchema,
      ),
  });
  const preview = useMutation({
    mutationFn: () =>
      api.request(
        '/api/theme-studio',
        { action: 'bitmap-preview', id: project.id, resource: resource.id, index },
        fileSchema,
      ),
  });
  const editable = resource.bitmaps?.every((b) => b.editable);
  return (
    <details className="p1-resource">
      <summary>
        {resource.name} · {resource.kind.toUpperCase()} · {bytes(resource.size)}
        {resource.bitmaps ? ` · ${resource.bitmaps.length} bitmap` : ''}
      </summary>
      <p>
        <code>{resource.target}</code>
      </p>
      <code className="p1-hash">{resource.sha256}</code>
      <div className="form-row">
        <button className="btn secondary" onClick={() => download.mutate()}>
          {t('Export resource', 'Экспорт ресурса')}
        </button>
        {project.mode === 'imported' && resource.editable && (
          <Field label={t('Replace whole resource', 'Заменить ресурс целиком')}>
            <input
              type="file"
              accept={`.${resource.kind}`}
              disabled={pending}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) upload(f, 'resource-replace');
                e.target.value = '';
              }}
            />
          </Field>
        )}
      </div>
      {download.data && <Download {...download.data} />}
      <ErrorMessage error={download.error ?? preview.error} />
      {resource.bitmaps && (
        <>
          <Field label={t('Bitmap index', 'Индекс битмапа')}>
            <select
              value={index}
              onChange={(e) => {
                setIndex(Number(e.target.value));
                preview.reset();
              }}
            >
              {resource.bitmaps.map((b) => (
                <option value={b.index} key={b.index}>
                  #{b.index} · {b.width}×{b.height} · {b.depth} bit
                </option>
              ))}
            </select>
          </Field>
          <div className="form-row">
            <button
              className="btn secondary"
              disabled={!editable || preview.isPending}
              onClick={() => preview.mutate()}
            >
              {t('Decode bitmap preview', 'Предпросмотр битмапа')}
            </button>
            {project.mode === 'imported' && editable && (
              <Field
                label={t(
                  'Replace bitmap with PNG (centre crop)',
                  'Заменить битмап на PNG (кадрирование по центру)',
                )}
              >
                <input
                  type="file"
                  accept="image/png"
                  disabled={pending}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) upload(f, 'bitmap-replace', index);
                    e.target.value = '';
                  }}
                />
              </Field>
            )}
          </div>
          {!editable && (
            <p className="note">
              {t(
                'This MBM contains unsupported depth/palette; use whole-resource replacement.',
                'MBM содержит неподдерживаемую глубину или палитру; замените ресурс целиком.',
              )}
            </p>
          )}
          {preview.data && (
            <img
              className="p1-bitmap"
              alt={t('Decoded bitmap', 'Декодированный битмап')}
              src={`data:image/png;base64,${preview.data.content}`}
            />
          )}
        </>
      )}
      <JsonReport value={resource.structure ?? resource.bitmaps} />
    </details>
  );
}
function PhonePreview({
  project,
  palette,
}: {
  project: ThemeProject;
  palette: Record<string, string>;
}) {
  const api = useApi(),
    { t } = usePreferences(),
    [view, setView] = useState('menu'),
    model = useProfiles().find((p) => p.value === project.profile)?.model,
    // Geometry and artwork come from the model registry; an unregistered profile falls back to 240×320.
    w = model?.screen?.width ?? 240,
    h = model?.screen?.height ?? 320,
    landscape = w > h;
  const image = useQuery({
    queryKey: ['theme-asset', project.id, project.revision],
    queryFn: ({ signal }) =>
      api.request(
        '/api/theme-studio',
        { action: 'asset', id: project.id, asset: 'wallpaper' },
        fileSchema,
        signal,
      ),
    enabled: project.wallpaper,
  });
  const p = palette;
  return (
    <>
      <div className="form-row">
        {['menu', 'list', 'dialog'].map((v) => (
          <button
            key={v}
            className={`btn ${v === view ? 'primary' : 'secondary'}`}
            onClick={() => setView(v)}
          >
            {v === 'menu'
              ? t('Menu', 'Меню')
              : v === 'list'
                ? t('List', 'Список')
                : t('Dialog', 'Диалог')}
          </button>
        ))}
      </div>
      <div className={`p1-theme-phone ${landscape ? 'p1-theme-phone--e72' : ''}`}>
        {model?.image ? (
          <img src={model.image} alt={model.name} />
        ) : (
          <span className="k-meta">
            {t('No artwork for this model', 'Для этой модели нет изображения')}
          </span>
        )}
        <div className="p1-theme-screen">
          <svg
            viewBox={`0 0 ${w} ${h}`}
            role="img"
            aria-label={`${t('Schematic theme preview', 'Схематичный предпросмотр темы')} ${w}×${h}`}
          >
            <rect width={w} height={h} fill={p.bg} />
            {project.mode === 'clear' && image.data && (
              <image width={w} height={h} href={`data:image/png;base64,${image.data.content}`} />
            )}
            <rect width={w} height={34} fill={p.status} />
            <text x="10" y="23" fontSize="17" fill={p.text}>
              {t('Menu', 'Меню')}
            </text>
            <text x={w - 52} y="22" fontSize="12" fill={p.text}>
              12:00
            </text>
            {view === 'menu' ? (
              Array.from({ length: landscape ? 6 : 9 }, (_, i) => {
                const x = 20 + (i % 3) * (w / 3),
                  y = 54 + Math.floor(i / 3) * 68;
                return (
                  <g key={i}>
                    {i === 0 && (
                      <rect
                        x={x - 10}
                        y={y - 7}
                        width={w / 3 - 2}
                        height={65}
                        rx="6"
                        fill={p.hl_fill_bot}
                      />
                    )}
                    <rect x={x + 10} y={y} width="30" height="30" rx="7" fill={p.accent} />
                    <text x={x + 25} y={y + 22} fontSize="20" textAnchor="middle" fill={p.panel}>
                      {['✉', '♫', '▤', '✦', '◷', '☷'][i % 6]}
                    </text>
                    <text
                      x={x + 25}
                      y={y + 49}
                      fontSize="10"
                      textAnchor="middle"
                      fill={i === 0 ? p.hl_text : p.text}
                    >
                      {
                        [
                          t('Messages', 'Сообщения'),
                          t('Music', 'Музыка'),
                          t('Files', 'Файлы'),
                          t('Tools', 'Средства'),
                          t('Clock', 'Часы'),
                          t('Contacts', 'Контакты'),
                        ][i % 6]
                      }
                    </text>
                  </g>
                );
              })
            ) : (
              <>
                {[
                  t('Applications', 'Приложения'),
                  t('Personalisation', 'Персонализация'),
                  t('Connectivity', 'Подключение'),
                  t('Settings', 'Настройки'),
                ].map((label, i) => (
                  <g key={i}>
                    <rect
                      x="6"
                      y={42 + i * 36}
                      width={w - 12}
                      height="34"
                      fill={i === 0 ? p.hl_fill_bot : p.panel}
                    />
                    <text x="16" y={65 + i * 36} fontSize="15" fill={i === 0 ? p.hl_text : p.text}>
                      {label}
                    </text>
                  </g>
                ))}
                {view === 'dialog' && (
                  <g>
                    <rect
                      x="18"
                      y="72"
                      width={w - 36}
                      height="100"
                      rx="8"
                      fill={p.panel}
                      stroke={p.line}
                    />
                    <text x="30" y="103" fill={p.text} fontSize="16">
                      {t('Apply theme?', 'Применить тему?')}
                    </text>
                    <rect x="30" y="125" width={w - 60} height="30" rx="4" fill={p.hl_fill_bot} />
                    <text x={w / 2} y="146" textAnchor="middle" fontSize="14" fill={p.hl_text}>
                      {t('Select', 'Выбрать')}
                    </text>
                  </g>
                )}
              </>
            )}
            <rect y={h - 26} width={w} height="26" fill={p.softkey} />
            <text x="10" y={h - 8} fontSize="13" fill={p.softkey_text}>
              {t('Options', 'Функции')}
            </text>
            <text x={w - 10} y={h - 8} textAnchor="end" fontSize="13" fill={p.softkey_text}>
              {t('Exit', 'Выйти')}
            </text>
          </svg>
        </div>
      </div>
      <p className="note">
        {project.mode === 'imported'
          ? t(
              'Imported appearance is not decoded. This illustration shows CLEAR reference colours, not the imported theme. Use Emulator Lab for its actual appearance.',
              'Внешний вид импортированной темы не декодирован. Иллюстрация показывает эталонные цвета CLEAR, а не импортированную тему. Для её просмотра используйте Emulator Lab.',
            )
          : t(
              'Schematic preview at native resolution. Firmware controls the actual menu and resource placement.',
              'Схематичный предпросмотр в родном разрешении. Реальное меню и размещение ресурсов определяет прошивка.',
            )}
      </p>
    </>
  );
}

function IconAsset({ project, uid }: { project: ThemeProject; uid: string }) {
  const api = useApi();
  const state = useQuery({
    queryKey: ['theme-asset', project.id, project.revision, uid],
    queryFn: ({ signal }) =>
      api.request(
        '/api/theme-studio',
        { action: 'asset', id: project.id, asset: 'icon', uid },
        fileSchema,
        signal,
      ),
  });
  return (
    <>
      {state.data && (
        <img
          width="48"
          height="48"
          src={`data:image/png;base64,${state.data.content}`}
          alt={`UID ${uid}`}
        />
      )}
      <ErrorMessage error={state.error} />
    </>
  );
}
