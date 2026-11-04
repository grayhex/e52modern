import { useQuery } from '@tanstack/react-query';
import { useApi, usePreferences } from '../state/app';
import { catalogSchema } from '../api/catalog';
import { Field } from './workspace';
import { useWorkspace } from '../hooks/useWorkspace';
import type { PackageChoice } from '../utils/packages';
export function PackagePicker({
  value,
  onChange,
  deviceSource = false,
  labSources = [],
}: {
  value: PackageChoice;
  onChange: (next: PackageChoice) => void;
  deviceSource?: boolean;
  labSources?: { id: string; name: string }[];
}) {
  const api = useApi(),
    { t } = usePreferences(),
    state = useWorkspace();
  const catalog = useQuery({
    queryKey: ['catalog'],
    queryFn: ({ signal }) => api.request('/api/catalog', { action: 'list' }, catalogSchema, signal),
    enabled: value.source === 'catalog',
  });
  const list =
    value.source === 'build'
      ? state.data?.packages
      : value.source === 'library'
        ? state.data?.library
        : value.source === 'catalog'
          ? catalog.data?.apps.filter((a) => a.delivery === 'automatic')
          : value.source === 'lab'
            ? labSources
            : [];
  return (
    <div className="react-fields">
      <Field label={t('Package source', 'Источник пакета')}>
        <select
          value={value.source}
          onChange={(e) =>
            onChange({
              ...value,
              source: e.target.value,
              reference: '',
              kind: e.target.value === 'library' ? 'theme' : value.kind,
            })
          }
        >
          {[
            ['upload', 'Upload', 'Файл'],
            ['catalog', 'Catalog', 'Каталог'],
            ['library', 'Library', 'Библиотека'],
            ['build', 'Build', 'Сборка'],
            ...(deviceSource
              ? [
                  ['device', 'Phone file', 'Файл телефона'],
                  ['lab', 'Lab report', 'Отчёт эмулятора'],
                ]
              : []),
          ].map(([id, en, ru]) => (
            <option value={id} key={id}>
              {t(en ?? '', ru ?? '')}
            </option>
          ))}
        </select>
      </Field>
      {value.source === 'upload' ? (
        <Field label={t('Package (up to 32 MiB)', 'Пакет (до 32 МиБ)')}>
          <input
            type="file"
            accept=".sis,.sisx,.jar,.jad"
            onChange={(e) => onChange({ ...value, file: e.target.files?.[0] ?? null })}
          />
        </Field>
      ) : (
        value.source !== 'device' && (
          <Field label={t('Package', 'Пакет')}>
            <select
              value={value.reference}
              onChange={(e) => onChange({ ...value, reference: e.target.value })}
            >
              <option value="">{t('Choose package', 'Выберите пакет')}</option>
              {list?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
        )
      )}
      <Field label={t('Package type', 'Тип пакета')}>
        <select value={value.kind} onChange={(e) => onChange({ ...value, kind: e.target.value })}>
          <option value="app">{t('Application / game', 'Приложение / игра')}</option>
          <option value="theme">{t('Theme', 'Тема')}</option>
        </select>
      </Field>
    </div>
  );
}
