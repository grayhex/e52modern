import { encode } from '../utils/files';
import { useWorkspace } from '../hooks/useWorkspace';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { bytes } from '../utils/files';
import { packageLink } from '../utils/packages';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { objectSchema, packageSchema, payload, text, strings } from '../api/workspace';
import { Card, DeviceSelect, ErrorMessage, Reading } from '../components/ui';
import { Field, JsonReport } from '../components/workspace';

import { useDevices } from '../api/queries';
const steps = [
  ['identify', 'Model / RM / firmware', 'Модель / RM / прошивка'],
  ['backup', 'Backup and original theme', 'Копия и исходная тема'],
  ['transfer', 'Package transferred', 'Пакет передан'],
  ['install', 'Installation', 'Установка'],
  ['activate', 'Theme applied', 'Тема применена'],
  ['standby', 'Standby / softkeys', 'Ожидание / softkeys'],
  ['menus', 'Menus and navigation', 'Меню и навигация'],
  ['dialogs', 'Dialogs and fields', 'Диалоги и поля'],
  ['apps', 'Built-in applications', 'Стандартные приложения'],
  ['restart', 'Restart and recheck', 'Перезапуск и повторная проверка'],
  ['uninstall', 'Removal and original theme', 'Удаление и возврат темы'],
] as const;
export default function Workbench({
  page,
}: {
  page: 'themes' | 'apps' | 'device' | 'overview' | 'activity';
}) {
  const api = useApi(),
    { t, device, setDevice } = usePreferences(),
    cache = useQueryClient(),
    state = useWorkspace();
  const [project, setProject] = useState(''),
    [backend, setBackend] = useState<Record<string, string>>({}),
    [choice, setChoice] = useState(''),
    [selector, setSelector] = useState(''),
    [file, setFile] = useState<File | null>(null),
    [draft, setDraft] = useState<z.infer<typeof packageSchema> | null>(null),
    [protocol, setProtocol] = useState<z.infer<typeof objectSchema> | null>(null);
  const confirm = useConfirmedAction<z.infer<typeof objectSchema>>();
  const operation = useMutation({
    mutationFn: async (body: z.infer<typeof objectSchema>) =>
      api.request('/api/run', body, objectSchema),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ['workspace'] });
    },
  });
  const library = useMutation({
    mutationFn: async (body: z.infer<typeof objectSchema>) =>
      api.request('/api/library', body, packageSchema),
    onSuccess: (r) => setDraft(r),
  });
  const importTheme = useMutation({
    mutationFn: async () => {
      if (!file || !file.size || file.size > 8 * 1024 ** 2)
        throw Error(t('Choose SIS/SISX up to 8 MiB', 'Выберите SIS/SISX до 8 МиБ'));
      return library.mutateAsync({
        action: 'import',
        name: file.name,
        content: await encode(file),
      });
    },
  });
  const report = protocol ?? state.data?.device_report ?? {};
  const saveReport = useMutation({
    mutationFn: () => api.request('/api/device-report', payload(report), objectSchema),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ['workspace'] });
    },
  });
  function run(action: string, extra: z.infer<typeof objectSchema> = {}) {
    operation.mutate({ action, ...extra });
  }
  const packages =
    state.data?.packages.filter((p) =>
      page === 'themes' ? p.kind === 'theme' : page === 'apps' ? p.kind === 'app' : true,
    ) ?? [];
  const titles = {
    themes: ['Themes & library', 'Темы и библиотека'],
    apps: ['Development', 'Разработка'],
    device: ['Device testing', 'Испытания телефона'],
    overview: ['Environment', 'Среда'],
    activity: ['Activity', 'Операции'],
  } as const;
  return (
    <>
      <h1>{t(titles[page][0], titles[page][1])}</h1>
      <ErrorMessage
        error={
          state.error ?? operation.error ?? library.error ?? importTheme.error ?? saveReport.error
        }
      />
      {page === 'themes' && (
        <>
          <Card>
            <h2>{t('Local theme library', 'Локальная библиотека тем')}</h2>
            <div className="form-row">
              <Field label="SIS / SISX">
                <input
                  type="file"
                  accept=".sis,.sisx"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </Field>
              <button
                className="btn secondary"
                disabled={!file || library.isPending}
                onClick={() => importTheme.mutate()}
              >
                {t('Upload & validate', 'Загрузить и проверить')}
              </button>
              <Field label={t('Built theme', 'Собранная тема')}>
                <select value={choice} onChange={(e) => setChoice(e.target.value)}>
                  <option value="">—</option>
                  {packages.map((p) => (
                    <option value={p.id} key={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </Field>
              <button
                className="btn secondary"
                disabled={!choice}
                onClick={() => library.mutate({ action: 'prepare-build', package: choice })}
              >
                {t('Prepare publication', 'Подготовить публикацию')}
              </button>
            </div>
            {draft && (
              <>
                <JsonReport value={draft} />
                <button
                  className="btn primary"
                  onClick={() =>
                    confirm.ask(
                      `${t('Publish locally', 'Опубликовать локально')}: ${draft.name}?`,
                      { endpoint: 'library', action: 'publish', id: draft.id },
                    )
                  }
                >
                  {t('Publish locally', 'Опубликовать локально')}
                </button>
              </>
            )}
            <DeviceSelect value={device} onChange={setDevice} capability="transfer" />
            {state.data?.library.map((p) => (
              <div className="package-row" key={p.id}>
                <strong>{p.name}</strong>
                <span>{bytes(p.size)}</span>
                <a
                  className="text-link"
                  href={'/api/library/download?id=' + encodeURIComponent(p.id)}
                  download={p.name}
                >
                  {t('Download', 'Скачать')}
                </a>
                <a className="btn ghost" href={packageLink('lab', 'library', p.id, 'theme')}>
                  {t('Test in emulator', 'Проверить в эмуляторе')}
                </a>
                <a className="btn ghost" href={packageLink('inspector', 'library', p.id, 'theme')}>
                  {t('Inspect', 'Анализ')}
                </a>
                <button
                  className="btn secondary"
                  disabled={!device}
                  onClick={() =>
                    confirm.ask(
                      `${t('Transfer without installing', 'Передать без установки')}: ${p.name}?`,
                      { endpoint: 'library-transfer', id: p.id, name: p.name },
                    )
                  }
                >
                  {t('Send to phone', 'Передать на телефон')}
                </button>
              </div>
            ))}
          </Card>
          <div className="themes-grid">
            {['light', 'dark'].map((variant) => (
              <Card key={variant}>
                <img
                  className="react-theme-preview"
                  src={'/api/preview/' + variant}
                  alt={`E52 CLEAR ${variant}`}
                />
                <h2>E52 CLEAR {variant}</h2>
                <a className="text-link" href={'/api/wallpaper/' + variant} download>
                  {t('Wallpaper PNG', 'Обои PNG')} ↓
                </a>
                <div className="form-row">
                  {['build', 'inspect'].map((action) => (
                    <button
                      className="btn secondary"
                      key={action}
                      onClick={() => run('theme.' + action, { variant })}
                    >
                      {action === 'build' ? t('Build', 'Собрать') : t('Check', 'Проверить')}
                    </button>
                  ))}
                  <Field label={t('Packager', 'Упаковщик')}>
                    <select
                      value={backend[variant] ?? 'auto'}
                      onChange={(e) => setBackend({ ...backend, [variant]: e.target.value })}
                    >
                      <option value="auto">Auto / MakeSIS</option>
                      <option value="makesis">MakeSIS</option>
                      <option value="native">
                        Native · {t('experimental', 'экспериментальный')}
                      </option>
                    </select>
                  </Field>
                  <button
                    className="btn primary"
                    onClick={() => {
                      const data = {
                        action: 'theme.package',
                        variant,
                        backend: backend[variant] ?? 'auto',
                      };
                      if (data.backend === 'native')
                        confirm.ask(
                          t(
                            'Build an experimental unsigned native SIS?',
                            'Собрать экспериментальный неподписанный native SIS?',
                          ),
                          data,
                        );
                      else operation.mutate(data);
                    }}
                  >
                    {t('Create SIS', 'Создать SIS')}
                  </button>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
      {page === 'apps' && (
        <>
          <Card>
            <div className="form-row">
              <Field label={t('New project', 'Новый проект')}>
                <input
                  maxLength={40}
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                />
              </Field>
              <button
                className="btn primary"
                disabled={!project || operation.isPending}
                onClick={() => run('app.init', { project })}
              >
                {t('Create', 'Создать')}
              </button>
            </div>
          </Card>
          <Card>
            {state.data?.projects.map((name) => (
              <div className="project-row" key={name}>
                <strong>{name}</strong>
                <div className="project-actions">
                  {[
                    ['build', 'Build', 'Собрать'],
                    ['inspect', 'Inspect', 'Инспектор'],
                    ['analyze', 'Compatibility', 'Совместимость'],
                    ['package', 'SIS', 'SIS'],
                  ].map(([action, en, ru]) => (
                    <button
                      key={action}
                      className="btn ghost"
                      disabled={operation.isPending}
                      onClick={() => run('app.' + action, { project: name })}
                    >
                      {t(en ?? '', ru ?? '')}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </Card>
        </>
      )}
      {page === 'overview' && (
        <Card>
          <h2>{t('Tool diagnostics', 'Диагностика инструментов')}</h2>
          <button
            className="btn primary"
            disabled={operation.isPending}
            onClick={() => run('doctor')}
          >
            {t('Check tools', 'Проверить инструменты')}
          </button>
          <JsonReport value={state.data?.jobs.find((j) => j.action === 'doctor')?.report ?? {}} />
        </Card>
      )}
      {page === 'device' && (
        <>
          <Card>
            <div className="form-row">
              {[
                ['device.list', 'Find server USB', 'Найти USB сервера'],
                ['device.info', 'Device info', 'Информация'],
                ['emulator.list', 'Emulators', 'Эмуляторы'],
              ].map(([action, en, ru]) => (
                <button
                  key={action}
                  className="btn secondary"
                  onClick={() => run(action ?? '', { selector })}
                >
                  {t(en ?? '', ru ?? '')}
                </button>
              ))}
            </div>
            <Field label={t('Server USB selector', 'USB устройства сервера')}>
              <input value={selector} onChange={(e) => setSelector(e.target.value)} />
            </Field>
            <p className="note">
              {t(
                'These commands target the server. Use Connection for Windows Bridge.',
                'Эти команды работают с сервером. Для Windows Bridge откройте Подключение.',
              )}
            </p>
            <Field label={t('Build package', 'Пакет сборки')}>
              <select value={choice} onChange={(e) => setChoice(e.target.value)}>
                <option value="">—</option>
                {packages.map((p) => (
                  <option value={p.id} key={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="form-row">
              {['sis.inspect', 'device.stage', 'emulator.test'].map((action) => (
                <button
                  key={action}
                  className="btn secondary"
                  disabled={!choice || operation.isPending}
                  onClick={() => {
                    const data = { action, package: choice, selector };
                    if (action === 'device.stage')
                      confirm.ask(
                        t(
                          'Copy SIS to server USB device? Complete installation on Nokia.',
                          'Передать SIS на USB-устройство сервера? Завершите установку на Nokia.',
                        ),
                        data,
                      );
                    else operation.mutate(data);
                  }}
                >
                  {action}
                </button>
              ))}
            </div>
          </Card>
          <Card>
            <h2>{t('Manual test protocol', 'Ручной протокол испытаний')}</h2>
            <a className="text-link" href="/api/device-report" download>
              {t('Download JSON', 'Скачать JSON')}
            </a>
            <div className="react-fields">
              {['rm', 'firmware', 'notes'].map((k) => (
                <Field key={k} label={k === 'notes' ? t('Notes', 'Заметки') : k}>
                  <input
                    value={text(report[k])}
                    onChange={(e) => setProtocol({ ...report, [k]: e.target.value })}
                  />
                </Field>
              ))}
            </div>
            {steps.map(([id, en, ru]) => (
              <div className="check-row" key={id}>
                <span>{t(en, ru)}</span>
                <select
                  aria-label={t(en, ru)}
                  value={text(objectSchema.catch({}).parse(report.steps)[id]) || 'pending'}
                  onChange={(e) =>
                    setProtocol({
                      ...report,
                      steps: {
                        ...objectSchema.catch({}).parse(report.steps),
                        [id]: e.target.value,
                      },
                    })
                  }
                >
                  {[
                    ['pending', 'Not tested', 'Не проверено'],
                    ['pass', 'Pass', 'Пройдено'],
                    ['fail', 'Fail', 'Ошибка'],
                    ['not-applicable', 'Not applicable', 'Не применимо'],
                  ].map(([v, en, ru]) => (
                    <option value={v} key={v}>
                      {t(en ?? '', ru ?? '')}
                    </option>
                  ))}
                </select>
              </div>
            ))}
            <button
              className="btn primary"
              disabled={saveReport.isPending}
              onClick={() => saveReport.mutate()}
            >
              {t('Save protocol', 'Сохранить протокол')}
            </button>
          </Card>
        </>
      )}
      {['themes', 'apps', 'device'].includes(page) && (
        <Card>
          <h2>{t('Packages', 'Пакеты')}</h2>
          {packages.map((p) => (
            <div className="package-row" key={p.id}>
              <strong>{p.name}</strong>
              <span>
                {p.source} · {bytes(p.size)}
              </span>
              <a
                className="text-link"
                href={'/api/download?id=' + encodeURIComponent(p.id)}
                download={p.name}
              >
                {t('Download', 'Скачать')}
              </a>
              <a className="btn ghost" href={packageLink('inspector', 'build', p.id, p.kind)}>
                {t('Inspect', 'Анализ')}
              </a>
              <a className="btn ghost" href={packageLink('lab', 'build', p.id, p.kind)}>
                {t('Test in emulator', 'Проверить в эмуляторе')}
              </a>
            </div>
          ))}
        </Card>
      )}
      {['activity', 'overview', 'apps', 'themes', 'device'].includes(page) && (
        <Card>
          <h2>{t('Activity', 'Операции')}</h2>
          {state.data?.jobs.map((job) => (
            <article className="job" key={job.id}>
              <div className="job-head">
                <strong>{job.command}</strong>
                <span className={'status ' + job.status}>{job.status}</span>
              </div>
              <p>{job.started}</p>
              <details open={job.status === 'running'}>
                <summary>{t('Output and report', 'Вывод и отчёт')}</summary>
                <pre>{job.output}</pre>
                {job.report && <JsonReport value={job.report} />}
              </details>
            </article>
          ))}
        </Card>
      )}
      {confirm.dialog(async (body) => {
        const data = { ...body };
        delete data.endpoint;
        if (body.endpoint === 'library') {
          await api.request('/api/library', { ...data, confirm: true }, objectSchema);
          setDraft(null);
        } else if (body.endpoint === 'library-transfer') {
          const r = await fetch('/api/library/download?id=' + encodeURIComponent(text(body.id)));
          if (!r.ok) throw Error('Download failed');
          await api.request(
            '/api/manager',
            {
              action: 'transfer',
              device,
              path: text(body.name),
              content: await encode(await r.blob()),
              confirm: true,
            },
            objectSchema,
          );
        } else await operation.mutateAsync(data);
        await cache.invalidateQueries({ queryKey: ['workspace'] });
      })}
    </>
  );
}
export function Updates() {
  const { t, device, setDevice } = usePreferences(),
    devices = useDevices(),
    phone = devices.data?.devices.find((d) => d.id === device);
  const messages: Record<string, [string, string]> = {
    older: [
      'A newer version is listed. Device flashing is disabled until a verified recovery procedure is available.',
      'В справочнике есть новая версия. Прошивка телефона отключена до появления проверенной процедуры восстановления.',
    ],
    'current-in-reference': [
      'Matches the local reference.',
      'Соответствует локальному справочнику.',
    ],
    'newer-than-reference': ['Newer than the local reference.', 'Новее локального справочника.'],
  };
  const message = messages[phone?.firmware_update?.status ?? ''] ?? [
    'Read an identifiable E52/E72 and firmware first.',
    'Сначала прочитайте модель E52/E72 и версию прошивки.',
  ];
  return (
    <>
      <h1>{t('Firmware updates', 'Обновления прошивки')}</h1>
      <Card>
        <DeviceSelect value={device} onChange={setDevice} />
        <dl className="dashboard-grid">
          {[
            [t('Model', 'Модель'), phone?.model],
            ['RM', phone?.rm],
            [t('Firmware', 'Прошивка'), phone?.firmware],
            [
              t('Latest in reference', 'Последняя в справочнике'),
              phone?.firmware_update?.latest_known,
            ],
          ].map(([label, value]) => (
            <div className="dashboard-metric" key={label}>
              <dt>{label}</dt>
              <dd>
                <Reading value={value} />
              </dd>
            </div>
          ))}
        </dl>
        <p>{t(message[0], message[1])}</p>
        {strings(phone?.firmware_update?.sources)
          .filter((s) => s.startsWith('https://'))
          .map((s) => (
            <p key={s}>
              <a href={s} className="text-link" target="_blank" rel="noreferrer">
                {s}
              </a>
            </p>
          ))}
      </Card>
    </>
  );
}
