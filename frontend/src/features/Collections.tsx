import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { useDevices } from '../api/queries';
import { catalogSchema } from '../api/catalog';
import { collectionSchema, collectionsSchema, recoverySchema, type Collection } from '../api/p1';
import { objectSchema, payload } from '../api/workspace';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
import { Download, Field, JsonReport } from '../components/workspace';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
const statuses: Record<string, [string, string]> = {
  'ready-for-transfer': ['Ready to transfer', 'Готово к передаче'],
  manual: ['Author download', 'Источник автора'],
  changed: ['Review version / hash', 'Проверьте версию / хеш'],
  unsupported: ['Unsupported', 'Не поддерживается'],
  unresolved: ['Missing from catalog', 'Нет в каталоге'],
  'blocked-dependency': ['Resolve dependency', 'Проверьте зависимость'],
};
export default function Collections() {
  const api = useApi(),
    cache = useQueryClient(),
    { t, device, setDevice } = usePreferences(),
    devices = useDevices();
  const state = useQuery({
      queryKey: ['collections'],
      queryFn: ({ signal }) =>
        api.request('/api/catalog', { action: 'collections' }, collectionsSchema, signal),
    }),
    catalog = useQuery({
      queryKey: ['catalog'],
      queryFn: ({ signal }) =>
        api.request('/api/catalog', { action: 'list' }, catalogSchema, signal),
    });
  const [id, setId] = useState(''),
    [name, setName] = useState(''),
    [profile, setProfile] = useState('nokia-e52'),
    [selected, setSelected] = useState<Set<string>>(new Set()),
    [search, setSearch] = useState(''),
    [path, setPath] = useState(''),
    [partial, setPartial] = useState(false),
    [json, setJson] = useState(''),
    [message, setMessage] = useState('');
  const plan = useMutation({
    mutationFn: () =>
      api.request('/api/catalog', { action: 'recovery-plan', id, profile, device }, recoverySchema),
  });
  const operation = useMutation({
    mutationFn: async (body: z.infer<typeof objectSchema>) =>
      api.request('/api/catalog', body, objectSchema),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ['collections'] });
      await cache.invalidateQueries({ queryKey: ['catalog'] });
    },
  });
  const importer = useMutation({
    mutationFn: async (file: File) => {
      if (file.size > 128 * 1024)
        throw Error(t('Collection limit: 128 KiB', 'Лимит набора: 128 КиБ'));
      const document: unknown = JSON.parse(await file.text());
      return operation.mutateAsync({
        action: 'collection-import',
        document: objectSchema.parse(document),
      });
    },
    onSuccess: (r) => {
      load(collectionSchema.parse(r));
      invalidate();
    },
  });
  const confirm = useConfirmedAction<'transfer' | 'delete'>();
  const current = state.data?.collections.find((c) => c.id === id);
  const dirty =
    !!current &&
    (current.name !== name ||
      current.apps.length !== selected.size ||
      current.apps.some((a) => !selected.has(a.id)));
  const phone = devices.data?.devices.find((d) => d.id === device);
  function load(collection: Collection) {
    setId(collection.id);
    setName(collection.name);
    setProfile(collection.profile);
    setSelected(new Set(collection.apps.map((a) => a.id)));
    plan.reset();
    setJson('');
    setMessage('');
  }
  function invalidate() {
    plan.reset();
    setPartial(false);
  }
  return (
    <>
      <Card>
        <div className="card-head">
          <h2>{t('App collections & recovery', 'Наборы и восстановление приложений')}</h2>
          <span className="chip">JSON · SHA-256</span>
        </div>
        <p className="note">
          {t(
            'Collections preserve catalog IDs, versions and package hashes, not phone data or installation state. Review a recovery plan for your new/reset phone before transferring files.',
            'Наборы сохраняют ID каталога, версии и хеши пакетов, а не личные данные или установленное состояние. Перед передачей на новый или сброшенный телефон проверьте план восстановления.',
          )}
        </p>
        <div className="form-row">
          {state.data?.templates.map((template) => (
            <button
              className="btn secondary"
              key={template.id}
              onClick={() => {
                setId('');
                setName(t(template.en, template.ru));
                setSelected(new Set(template.ids));
                invalidate();
              }}
            >
              {t(template.en, template.ru)}
            </button>
          ))}
          <button
            className="btn ghost"
            onClick={() => {
              setId('');
              setName('');
              setSelected(new Set());
              invalidate();
            }}
          >
            {t('New collection', 'Новый набор')}
          </button>
        </div>
        <div className="react-fields">
          <Field label={t('Saved collection', 'Сохранённый набор')}>
            <select
              value={id}
              onChange={(e) => {
                const c = state.data?.collections.find((c) => c.id === e.target.value);
                if (c) load(c);
              }}
            >
              <option value="">{t('Unsaved selection', 'Несохранённый выбор')}</option>
              {state.data?.collections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} · {c.profile}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('Collection name', 'Название набора')}>
            <input
              maxLength={60}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                invalidate();
              }}
            />
          </Field>
          <Field label={t('Phone profile', 'Профиль телефона')}>
            <select
              value={profile}
              onChange={(e) => {
                setProfile(e.target.value);
                invalidate();
              }}
            >
              {Object.entries(state.data?.profiles ?? {}).map(([id, p]) => (
                <option value={id} key={id}>
                  {p.model} · {p.screen.join('×')} · Symbian {p.symbian}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('Find application', 'Поиск приложения')}>
            <input value={search} onChange={(e) => setSearch(e.target.value)} />
          </Field>
        </div>
        <div className="p1-app-selection">
          {catalog.data?.apps
            .filter((a) =>
              `${a.name} ${a.description}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()),
            )
            .map((app) => (
              <label key={app.id}>
                <input
                  type="checkbox"
                  checked={selected.has(app.id)}
                  onChange={(e) => {
                    setSelected((old) => {
                      const next = new Set(old);
                      if (e.target.checked) next.add(app.id);
                      else next.delete(app.id);
                      return next;
                    });
                    invalidate();
                  }}
                />
                <span>
                  {app.name}{' '}
                  <small>
                    {app.version} ·{' '}
                    {app.delivery === 'manual'
                      ? t('Author download', 'Скачать у автора')
                      : t('Automatic download', 'Автозагрузка')}{' '}
                    · {app.compatibility}
                  </small>
                </span>
              </label>
            ))}
        </div>
        {[...selected]
          .filter((key) => !catalog.data?.apps.some((a) => a.id === key))
          .map((key) => (
            <p key={key} className="note">
              {key} · {t('Missing in current catalog', 'Нет в текущем каталоге')}{' '}
              <button
                className="btn ghost"
                onClick={() => {
                  setSelected((old) => new Set([...old].filter((id) => id !== key)));
                  invalidate();
                }}
              >
                {t('Remove from selection', 'Убрать из выбора')}
              </button>
            </p>
          ))}
        <div className="form-row">
          <button
            className="btn primary"
            disabled={!name.trim() || !selected.size || operation.isPending}
            onClick={() =>
              operation.mutate(
                payload({
                  action: 'collection-save',
                  name,
                  profile,
                  ids: [...selected],
                  ...(id ? { id } : {}),
                }),
                {
                  onSuccess: (r) => {
                    load(collectionSchema.parse(r));
                    invalidate();
                    setMessage(
                      t(
                        'Collection saved with current version/hash pins.',
                        'Набор сохранён с текущими версиями и хешами.',
                      ),
                    );
                  },
                },
              )
            }
          >
            {t('Save selection', 'Сохранить выбор')} ({selected.size})
          </button>
          <button
            className="btn secondary"
            disabled={!id || operation.isPending}
            onClick={() =>
              operation.mutate(
                { action: 'collection-export', id },
                {
                  onSuccess: (r) =>
                    setJson(btoa(unescape(encodeURIComponent(JSON.stringify(r, null, 2))))),
                },
              )
            }
          >
            {t('Export collection JSON', 'Экспорт набора JSON')}
          </button>
          <Field label={t('Import collection JSON (128 KiB)', 'Импорт набора JSON (128 КиБ)')}>
            <input
              type="file"
              accept=".json"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                importer.mutate(file);
                e.target.value = '';
              }}
            />
          </Field>
          <button
            className="btn ghost"
            disabled={!id}
            onClick={() =>
              confirm.ask(
                t(
                  'Delete this local collection? Phone data is unaffected.',
                  'Удалить локальный набор? Данные телефона не затрагиваются.',
                ),
                'delete',
              )
            }
          >
            {t('Delete collection', 'Удалить набор')}
          </button>
        </div>
        {json && <Download name="symport-collection.json" content={json} mime="application/json" />}
        <p role="status">{message}</p>
        <ErrorMessage error={state.error ?? catalog.error ?? operation.error ?? importer.error} />
      </Card>
      <Card>
        <h2>{t('Recover on a phone', 'Восстановить набор на телефоне')}</h2>
        <div className="form-row">
          <DeviceSelect
            value={device}
            onChange={(id) => {
              setDevice(id);
              invalidate();
            }}
          />
          <button
            className="btn secondary"
            disabled={!id || dirty || plan.isPending}
            onClick={() => plan.mutate()}
          >
            {t('Preview recovery', 'План восстановления')}
          </button>
          <Field label={t('Destination folder', 'Папка назначения')}>
            <input
              value={path}
              disabled={phone?.capabilities.includes('opp-push')}
              onChange={(e) => setPath(e.target.value)}
            />
          </Field>
        </div>
        {dirty && (
          <p className="note">
            {t(
              'Save your selection before previewing recovery.',
              'Сохраните изменения набора перед просмотром плана восстановления.',
            )}
          </p>
        )}
        <ErrorMessage error={plan.error} />
        {plan.data && (
          <>
            <p>
              {String(plan.data.target.model)} · {String(plan.data.target.symbian)} ·{' '}
              {Array.isArray(plan.data.target.screen) ? plan.data.target.screen.join('×') : '—'}
            </p>
            {plan.data.geometry_changed && (
              <p className="note">
                {t(
                  'Screen geometry differs from the saved collection. Check fixed-resolution apps and UI orientation manually.',
                  'Геометрия экрана отличается от сохранённого набора. Проверьте приложения с фиксированным разрешением и ориентацию интерфейса.',
                )}
              </p>
            )}
            {plan.data.problems.map((p) => (
              <p className="error-text" key={p}>
                {p}
              </p>
            ))}
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>
                      {t('Application / dependency order', 'Приложение / порядок зависимостей')}
                    </th>
                    <th>{t('Recovery status', 'Статус восстановления')}</th>
                    <th>{t('Details', 'Подробности')}</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.data.rows.map((row) => (
                    <tr key={row.id}>
                      <td>{row.name}</td>
                      <td>
                        <span className="chip">
                          {t(...(statuses[row.status] ?? [row.status, row.status]))}
                        </span>
                        <br />
                        {row.compatibility}
                      </td>
                      <td>
                        {row.reasons.map((r) => (
                          <p key={r}>{r}</p>
                        ))}
                        {row.requirements.map((requirement) => (
                          <p className="note" key={requirement}>
                            {requirement}
                          </p>
                        ))}
                        {!!row.runtime_requirements.length && (
                          <>
                            <p className="note">
                              {t(
                                'Runtime availability on the phone is unknown.',
                                'Наличие runtime на телефоне неизвестно.',
                              )}{' '}
                              {row.runtime_requirements
                                .map((r) => `${String(r.name)} ${String(r.min_version ?? '')}`)
                                .join(' · ')}
                            </p>
                            <a
                              className="text-link"
                              href={`#apps/dependencies?${new URLSearchParams({ source: 'catalog', reference: row.id, profile })}`}
                            >
                              {t('Review package dependencies', 'Проверить зависимости пакета')} →
                            </a>
                          </>
                        )}
                        {row.status === 'manual' &&
                          row.sources
                            .filter((s) => s.startsWith('https://'))
                            .map((s) => (
                              <a
                                key={s}
                                className="text-link"
                                href={s}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {t('Author source', 'Источник автора')} ↗{' '}
                              </a>
                            ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ol>
              {plan.data.instructions.map((s) => (
                <li key={s.en}>{t(s.en, s.ru)}</li>
              ))}
            </ol>
            {plan.data.partial && (
              <label className="p1-consent">
                <input
                  type="checkbox"
                  checked={partial}
                  onChange={(e) => setPartial(e.target.checked)}
                />
                {t(
                  'Transfer only available applications; I will handle the other entries manually.',
                  'Передать только доступные приложения; остальные позиции обработаю вручную.',
                )}
              </label>
            )}
            <button
              className="btn primary"
              disabled={
                !device ||
                !plan.data.transfer_ids.length ||
                !!plan.data.problems.length ||
                (plan.data.partial && !partial) ||
                confirm.busy
              }
              onClick={() =>
                confirm.ask(
                  `${t('Transfer the previewed set? Complete installation on Nokia in dependency order.', 'Передать показанный набор? Завершите установку на Nokia в порядке зависимостей.')}\n${device}\n${plan.data?.transfer_ids.join(', ')}`,
                  'transfer',
                )
              }
            >
              {t('Transfer recovery set', 'Передать набор восстановления')}
            </button>
            <JsonReport value={plan.data} />
          </>
        )}
      </Card>
      {confirm.dialog(async (action) => {
        if (action === 'delete') {
          await operation.mutateAsync({ action: 'collection-delete', id, confirm: true });
          setId('');
          setName('');
          setSelected(new Set());
          invalidate();
          return;
        }
        if (!plan.data) throw Error('Preview recovery first');
        const preview = plan.data;
        plan.reset();
        await operation.mutateAsync({
          action: 'recovery-transfer',
          id,
          profile,
          device,
          path: phone?.capabilities.includes('opp-push') ? '' : path,
          confirm: true,
          preview_sha256: preview.preview_sha256,
          ack_partial: partial,
        });
        setMessage(
          t(
            'Transfer queued. Follow the catalog operation history; installation is completed on Nokia.',
            'Передача поставлена в очередь. Результаты — в журнале каталога; установка выполняется на Nokia.',
          ),
        );
      })}
      <p>
        <a className="text-link" href="#apps/catalog">
          {t('Open catalog transfer history', 'Открыть журнал передачи каталога')} →
        </a>
      </p>
    </>
  );
}
