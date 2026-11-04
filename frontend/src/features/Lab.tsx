import { bytes } from '../utils/files';
import { encode } from '../utils/files';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { initialChoice } from '../utils/packages';
import { packageLink } from '../utils/packages';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { labSchema, labReportSchema, uploadSchema, type LabReport } from '../api/lab';
import { objectSchema, payload, text } from '../api/workspace';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
import { Download, Field, JsonReport } from '../components/workspace';
import { PackagePicker } from '../components/PackagePicker';
const keyboard: Record<string, string> = {
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  Enter: 'ok',
  F1: 'lsk',
  F2: 'rsk',
  F3: 'applications',
  Backspace: 'clear',
  Escape: 'end',
  '*': 'star',
  '#': 'hash',
  ...Object.fromEntries(Array.from({ length: 10 }, (_, i) => [String(i), String(i)])),
};
const hardware = [
  ['lsk', 'Left softkey', 'Левая softkey'],
  ['rsk', 'Right softkey', 'Правая softkey'],
  ['applications', 'Menu / Home', 'Меню / Home'],
  ['call', 'Call', 'Вызов'],
  ['end', 'End', 'Отбой'],
  ['up', 'Up', 'Вверх'],
  ['down', 'Down', 'Вниз'],
  ['left', 'Left', 'Влево'],
  ['right', 'Right', 'Вправо'],
  ['ok', 'OK', 'OK'],
  ...Array.from({ length: 10 }, (_, i) => [String(i), String(i), String(i)]),
  ['star', '*', '*'],
  ['hash', '#', '#'],
] as const;
function Handset({
  running,
  reason,
  keys,
}: {
  running: boolean;
  reason: string | undefined;
  keys: Record<string, z.infer<typeof objectSchema>[string]> | undefined;
}) {
  const api = useApi(),
    { t } = usePreferences(),
    ref = useRef<HTMLDivElement>(null),
    held = useRef(new Map<string, string>()),
    queue = useRef<Promise<unknown>>(Promise.resolve()),
    [pressed, setPressed] = useState<Set<string>>(new Set()),
    [error, setError] = useState<unknown>(null);
  const frame = useQuery({
    queryKey: ['lab-frame'],
    queryFn: ({ signal }) =>
      api.request(
        '/api/lab',
        { action: 'frame' },
        z.object({ png: z.string(), width: z.number(), height: z.number() }),
        signal,
      ),
    enabled: running,
    refetchInterval: running ? 250 : false,
    refetchIntervalInBackground: false,
    gcTime: 0,
  });
  const send = useCallback(
    (key: string, event: string) => {
      queue.current = queue.current
        .catch(() => undefined)
        .then(() => api.request('/api/lab', { action: 'key', key, event }, objectSchema))
        .catch(setError);
    },
    [api],
  );
  const release = useCallback(() => {
    held.current.clear();
    setPressed(new Set());
    queue.current = queue.current
      .catch(() => undefined)
      .then(() => api.request('/api/lab', { action: 'release' }, objectSchema))
      .catch(() => undefined);
  }, [api]);
  useEffect(() => {
    const hide = () => {
      if (document.hidden) release();
    };
    addEventListener('blur', release);
    document.addEventListener('visibilitychange', hide);
    return () => {
      removeEventListener('blur', release);
      document.removeEventListener('visibilitychange', hide);
      release();
    };
  }, [release]);
  function press(source: string, key: string) {
    if (held.current.has(source)) return;
    const already = [...held.current.values()].includes(key);
    held.current.set(source, key);
    setPressed(new Set(held.current.values()));
    if (!already) send(key, 'down');
  }
  function lift(source: string) {
    const key = held.current.get(source);
    if (!key) return;
    held.current.delete(source);
    setPressed(new Set(held.current.values()));
    if (![...held.current.values()].includes(key)) send(key, 'up');
  }
  const disabled = (key: string) => !running || !!reason || (!!keys && !Object.hasOwn(keys, key));
  return (
    <>
      <div
        ref={ref}
        className="lab-handset"
        tabIndex={0}
        role="group"
        aria-label={t('Nokia E52 emulator keyboard', 'Клавиатура эмулятора Nokia E52')}
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget)) release();
        }}
        onKeyDown={(e) => {
          if (e.target instanceof HTMLButtonElement && ['Enter', ' '].includes(e.key)) return;
          const key = keyboard[e.key];
          if (!key || disabled(key) || e.ctrlKey || e.altKey || e.metaKey) return;
          e.preventDefault();
          press('key:' + e.code, key);
        }}
        onKeyUp={(e) => {
          if (held.current.has('key:' + e.code)) {
            e.preventDefault();
            lift('key:' + e.code);
          }
        }}
      >
        <img
          className="lab-e52-body"
          src={`${import.meta.env.BASE_URL}phones/nokia-e52-silver.png`}
          width="831"
          height="1893"
          alt={t('Silver Nokia E52', 'Серебристая Nokia E52')}
          draggable={false}
        />
        <div className="lab-screen">
          {running && frame.data && !frame.error ? (
            <img alt="EKA2L1" src={'data:image/png;base64,' + frame.data.png} />
          ) : (
            <div>
              {frame.error instanceof Error
                ? frame.error.message
                : t(
                    'Start your firmware to see the screen.',
                    'Запустите прошивку для просмотра экрана.',
                  )}
            </div>
          )}
        </div>
        {hardware.map(([key, en, ru]) => (
          <button
            key={key}
            className={`lab-e52-key lab-e52-${key} ${pressed.has(key) ? 'is-held' : ''}`}
            disabled={disabled(key)}
            aria-label={t(en ?? key, ru ?? key)}
            onPointerDown={(e) => {
              e.preventDefault();
              ref.current?.focus({ preventScroll: true });
              e.currentTarget.setPointerCapture(e.pointerId);
              press('pointer:' + e.pointerId, key);
            }}
            onPointerUp={(e) => lift('pointer:' + e.pointerId)}
            onPointerCancel={(e) => lift('pointer:' + e.pointerId)}
            onLostPointerCapture={(e) => lift('pointer:' + e.pointerId)}
            onClick={(e) => {
              if (e.detail === 0) {
                send(key, 'down');
                send(key, 'up');
              }
            }}
          >
            <span className="sr-only">{t(en ?? key, ru ?? key)}</span>
          </button>
        ))}
        <button
          className="lab-e52-key lab-e52-mail"
          disabled
          aria-label={t('Mail key unavailable in emulator API', 'Почта недоступна в API эмулятора')}
        />
      </div>
      <button
        className="btn ghost"
        disabled={disabled('clear')}
        onClick={() => {
          send('clear', 'down');
          send('clear', 'up');
        }}
      >
        {t('Clear / Backspace', 'Удалить / Backspace')}
      </button>
      <p className="muted">
        {t(
          'Click the phone: arrows, Enter, F1/F2 softkeys, F3 menu, Backspace, digits, * and #.',
          'Нажмите на телефон: стрелки, Enter, F1/F2 softkeys, F3 меню, Backspace, цифры, * и #.',
        )}
      </p>
      <p>{reason}</p>
      <ErrorMessage error={error} />
    </>
  );
}
export default function Lab() {
  const api = useApi(),
    cache = useQueryClient(),
    { t } = usePreferences();
  const state = useQuery({
    queryKey: ['lab'],
    queryFn: ({ signal }) => api.request('/api/lab', { action: 'state' }, labSchema, signal),
    refetchInterval: 2500,
  });
  const [code, setCode] = useState(''),
    [choice, setChoice] = useState(initialChoice),
    [reportId, setReportId] = useState(
      () => new URLSearchParams(location.hash.split('?')[1]).get('report') ?? '',
    );
  const confirm = useConfirmedAction<Record<string, z.infer<typeof objectSchema>[string]>>();
  const selectedCode = code || state.data?.health?.defaults?.symbian || '',
    running = state.data?.health?.instance?.running ?? false,
    busy = !!state.data?.active || confirm.busy,
    available = state.data?.available ?? false;
  const operation = useMutation({
    mutationFn: async (body: Record<string, z.infer<typeof objectSchema>[string]>) =>
      api.request('/api/lab', body, objectSchema),
    onSuccess: async (r) => {
      if (r.id) setReportId(text(r.id));
      await cache.invalidateQueries({ queryKey: ['lab'] });
    },
  });
  return (
    <>
      <h1>Emulator Lab</h1>
      <Card>
        <div className="card-head">
          <h2>EKA2L1 / MGO</h2>
          <span className="chip">
            {available ? t('Connected', 'Подключён') : t('Unavailable', 'Недоступен')}
          </span>
        </div>
        <p>{state.data?.reason}</p>
        {!available && <p className="note">docker compose --profile emulator up -d --build</p>}
        <ErrorMessage error={state.error ?? operation.error} />
      </Card>
      <div className="lab-workspace">
        <div className="lab-phone-panel card">
          <Field label={t('Installed firmware', 'Установленная прошивка')}>
            <select
              disabled={!available || busy}
              value={selectedCode}
              onChange={(e) => {
                setCode(e.target.value);
                if (e.target.value) operation.mutate({ action: 'select', code: e.target.value });
              }}
            >
              <option value="">{t('Choose firmware', 'Выберите прошивку')}</option>
              {state.data?.health?.firmware?.devices.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.manufacturer} {d.model} · {d.code}
                </option>
              ))}
            </select>
          </Field>
          <div className="form-row lab-session">
            <button
              className="btn primary"
              disabled={!available || !selectedCode || busy}
              onClick={() => operation.mutate({ action: 'start', code: selectedCode })}
            >
              {t('Start', 'Запустить')}
            </button>
            <button
              className="btn secondary"
              disabled={!available || !selectedCode || busy}
              onClick={() =>
                confirm.ask(
                  t(
                    'Restart virtual phone? The current application will stop.',
                    'Перезапустить виртуальный телефон? Текущее приложение остановится.',
                  ),
                  { action: 'reboot', code: selectedCode },
                )
              }
            >
              {t('Restart', 'Перезапуск')}
            </button>
            <button
              className="btn secondary"
              disabled={
                !running ||
                state.data?.reports.some(
                  (r) => r.id === state.data?.active && r.kind === 'firmware',
                ) ||
                operation.isPending
              }
              onClick={() => operation.mutate({ action: 'stop' })}
            >
              {t('Stop', 'Стоп')}
            </button>
          </div>
          <Handset
            running={running}
            reason={state.data?.control_reason}
            keys={state.data?.keys?.keys}
          />
        </div>
        <div className="lab-tools">
          <Firmware state={state.data} onReport={setReportId} />
          <Card>
            <h2>{t('Package test', 'Проверка пакета')}</h2>
            <PackagePicker value={choice} onChange={setChoice} />
            <p className="note">
              {t(
                'Apply themes manually through Symbian Settings → Themes. Themes are not launched by UID. JAR/JAD is unsupported here: MGO KEmulator is separate from Symbian Java ME.',
                'Применяйте темы вручную через Параметры → Темы в Symbian. Тема не запускается по UID. JAR/JAD здесь не поддерживается: KEmulator MGO отличается от Symbian Java ME.',
              )}
            </p>
            <button
              className="btn primary"
              disabled={!available || !selectedCode || busy}
              onClick={() =>
                confirm.ask(
                  t(
                    'Install this package in the emulator? This does not prove physical-phone compatibility.',
                    'Установить пакет в эмуляторе? Это не доказывает совместимость с телефоном.',
                  ),
                  { action: 'test' },
                )
              }
            >
              {t('Test in emulator', 'Проверить в эмуляторе')}
            </button>
          </Card>
          <Card>
            <h2>{t('Reports', 'Отчёты')}</h2>
            <div className="lab-report-list">
              {state.data?.reports.map((r) => (
                <button className="lab-report-row" key={r.id} onClick={() => setReportId(r.id)}>
                  <strong>{r.package?.name ?? r.kind}</strong>
                  <span className={'status ' + r.status}>
                    {r.running ? t('Working…', 'Выполняется…') : r.status}
                  </span>
                  <small>{r.created}</small>
                </button>
              ))}
            </div>
          </Card>
        </div>
      </div>
      {reportId && (
        <Report
          key={reportId}
          id={reportId}
          current={state.data?.current === reportId}
          running={running}
        />
      )}
      <p className="disclaimer">
        {t(
          'Emulator success does not confirm operation on a physical Nokia. Hardware, certificates, services and firmware support depend on EKA2L1. Guest network is isolated; audio and touch are unavailable in this UI.',
          'Успех в эмуляторе не подтверждает работу на настоящей Nokia. Поддержка оборудования, сертификатов, служб и прошивки зависит от EKA2L1. Сеть гостя изолирована; звук и сенсорное управление здесь недоступны.',
        )}
      </p>
      {confirm.dialog(async (body) => {
        await api.request('/api/lab', { action: 'release' }, objectSchema).catch(() => undefined);
        let data = body;
        if (body.action === 'test') {
          data = payload({
            action: 'test',
            source: choice.source,
            reference: choice.reference,
            kind: choice.kind,
            code: selectedCode,
            confirm: true,
          });
          if (choice.source === 'upload') {
            if (!choice.file || choice.file.size > 32 * 1024 ** 2)
              throw Error('Package limit: 32 MiB');
            data.name = choice.file.name;
            data.content = await encode(choice.file);
          }
        }
        await operation.mutateAsync(data);
      })}
    </>
  );
}
function Firmware({
  state,
  onReport,
}: {
  state: z.infer<typeof labSchema> | undefined;
  onReport: (id: string) => void;
}) {
  const api = useApi(),
    cache = useQueryClient(),
    { t } = usePreferences(),
    [format, setFormat] = useState('rom'),
    [rom, setRom] = useState<File | null>(null),
    [rpkg, setRpkg] = useState<File | null>(null),
    [files, setFiles] = useState<File[]>([]),
    [variant, setVariant] = useState(''),
    [ids, setIds] = useState<Set<string>>(new Set()),
    [progress, setProgress] = useState(0),
    confirm = useConfirmedAction<string[]>();
  const upload = useMutation({
    mutationFn: async () => {
      let slots: [string, File][] = [];
      let bundle = '';
      if (format === 'rom') {
        if (rom) slots.push(['rom', rom]);
        if (rpkg) slots.push(['rpkg', rpkg]);
        if (!rom) throw Error('Choose ROM');
      } else if (format === 'archive') {
        if (files[0]) slots = [['archive', files[0]]];
      } else {
        slots = files.map((f) => [f.name.toLowerCase().endsWith('.vpl') ? 'vpl' : 'fpsx', f]);
        if (slots.filter(([slot]) => slot === 'vpl').length !== 1)
          throw Error('Choose one VPL and its FPSX files');
        bundle = (
          await api.request('/api/lab', { action: 'bundle' }, z.object({ bundle: z.string() }))
        ).bundle;
      }
      if (
        !slots.length ||
        slots.some(
          ([s, f]) => !f.size || f.size > 2 * 1024 ** 3 || (s === 'vpl' && f.size > 4 * 1024 ** 2),
        )
      )
        throw Error('Firmware limit: 2 GiB/file; VPL: 4 MiB');
      setIds(new Set());
      const uploaded: string[] = [];
      for (const [slot, file] of slots) {
        const r = await api.uploadProgress(
          '/api/lab/firmware?' +
            new URLSearchParams({ slot, name: file.name, ...(bundle ? { bundle } : {}) }),
          file,
          uploadSchema,
          setProgress,
        );
        uploaded.push(r.id);
      }
      setIds(new Set(uploaded));
      await cache.invalidateQueries({ queryKey: ['lab'] });
    },
  });
  const busy = upload.isPending || confirm.busy || !!state?.active;
  return (
    <Card>
      <details open>
        <summary>{t('Your emulator firmware', 'Ваша прошивка эмулятора')}</summary>
        <p>
          {t(
            'Use your own firmware. ROM, proprietary files and keys are not included. Preserve original VPL/FPSX names.',
            'Используйте свою прошивку. ROM, проприетарные файлы и ключи не включены. Сохраняйте исходные имена VPL/FPSX.',
          )}
        </p>
        <Field label={t('Format', 'Формат')}>
          <select
            value={format}
            disabled={busy}
            onChange={(e) => {
              setFormat(e.target.value);
              setFiles([]);
              setIds(new Set());
            }}
          >
            <option value="rom">ROM + RPKG</option>
            <option value="archive">{t('Archive', 'Архив')}</option>
            <option value="vpl">VPL + FPSX</option>
          </select>
        </Field>
        {format === 'rom' ? (
          <div className="react-fields">
            <Field label="ROM">
              <input type="file" onChange={(e) => setRom(e.target.files?.[0] ?? null)} />
            </Field>
            <Field label="RPKG">
              <input
                type="file"
                accept=".rpkg"
                onChange={(e) => setRpkg(e.target.files?.[0] ?? null)}
              />
            </Field>
          </div>
        ) : (
          <Field label={format === 'vpl' ? 'VPL + FPSX' : 'ZIP / 7Z / RAR'}>
            <input
              type="file"
              multiple={format === 'vpl'}
              accept={format === 'vpl' ? '.vpl,.fpsx' : '.zip,.7z,.rar'}
              onChange={(e) => setFiles([...(e.target.files ?? [])])}
            />
          </Field>
        )}
        {format === 'vpl' && (
          <Field label={t('Variant index (optional)', 'Индекс варианта (необязательно)')}>
            <input
              type="number"
              min="0"
              max="65535"
              value={variant}
              onChange={(e) => setVariant(e.target.value)}
            />
          </Field>
        )}
        <div className="form-row">
          <button
            className="btn secondary"
            disabled={!state?.available || busy}
            onClick={() => upload.mutate()}
          >
            {t('Upload files', 'Загрузить файлы')}
          </button>
          <button
            className="btn primary"
            disabled={!state?.available || busy || !ids.size}
            onClick={() =>
              confirm.ask(
                t(
                  'Install selected firmware? Current virtual session will stop.',
                  'Установить выбранную прошивку? Текущий виртуальный сеанс остановится.',
                ),
                [...ids],
              )
            }
          >
            {t('Install firmware', 'Установить прошивку')}
          </button>
        </div>
        {upload.isPending && (
          <progress
            max="100"
            value={progress}
            aria-label={t('Firmware upload', 'Загрузка прошивки')}
          />
        )}
        <ErrorMessage error={upload.error} />
        <div className="lab-upload-list">
          {Object.values(state?.uploads ?? {})
            .slice(-30)
            .reverse()
            .map((f) => (
              <label className="lab-upload-entry" key={f.id}>
                <input
                  type="checkbox"
                  disabled={busy || !!f.consumed}
                  checked={ids.has(f.id)}
                  onChange={(e) =>
                    setIds((current) => {
                      const next = new Set(current);
                      if (e.target.checked) next.add(f.id);
                      else next.delete(f.id);
                      return next;
                    })
                  }
                />
                {f.slot} · {f.name} · {bytes(f.size)} {f.consumed ? '✓' : ''}
              </label>
            ))}
        </div>
      </details>
      {confirm.dialog(async (uploads) => {
        const r = await api.request(
          '/api/lab',
          payload({
            action: 'install-firmware',
            uploads,
            confirm: true,
            ...(format === 'vpl' && variant !== '' ? { variant: Number(variant) } : {}),
          }),
          labReportSchema,
        );
        onReport(r.id);
        setIds(new Set());
        await cache.invalidateQueries({ queryKey: ['lab'] });
      })}
    </Card>
  );
}
function Report({ id, current, running }: { id: string; current: boolean; running: boolean }) {
  const api = useApi(),
    { t, device, setDevice } = usePreferences(),
    [path, setPath] = useState(''),
    [step, setStep] = useState('applied'),
    [result, setResult] = useState('pass'),
    [logs, setLogs] = useState<z.infer<typeof objectSchema> | null>(null),
    confirm = useConfirmedAction<string>();
  const report = useQuery({
    queryKey: ['lab-report', id],
    queryFn: ({ signal }) =>
      api.request('/api/lab', { action: 'report', id }, labReportSchema, signal),
    refetchInterval: 2500,
  });
  const r = report.data;
  const action = useMutation({
    mutationFn: async (body: z.infer<typeof objectSchema>) =>
      api.request('/api/lab', { id, ...body }, objectSchema),
    onSuccess: async () => {
      await report.refetch();
    },
  });
  const ready =
    current && running && !r?.running && r?.events?.some((e) => e.stage === 'firmware-booted');
  return (
    <Card>
      <h2>{r?.package?.name ?? t('Session report', 'Отчёт сеанса')}</h2>
      <ErrorMessage error={report.error ?? action.error} />
      {r && (
        <>
          <dl className="device-details">
            {['status', 'engine', 'install', 'launch', 'physical_device', 'firmware'].map((k) => (
              <div key={k}>
                <dt>
                  {t(
                    {
                      status: 'Status',
                      engine: 'Engine',
                      install: 'Installation',
                      launch: 'Launch',
                      physical_device: 'Physical phone',
                      firmware: 'Firmware',
                    }[k] ?? k,
                    {
                      status: 'Статус',
                      engine: 'Движок',
                      install: 'Установка',
                      launch: 'Запуск',
                      physical_device: 'Физическая Nokia',
                      firmware: 'Прошивка',
                    }[k] ?? k,
                  )}
                </dt>
                <dd className="lab-value">
                  {typeof r[k] === 'object' ? JSON.stringify(r[k]) : text(r[k])}
                </dd>
              </div>
            ))}
            <div>
              <dt>SHA-256</dt>
              <dd className="lab-value">{r.package?.sha256}</dd>
            </div>
          </dl>
          {['error', 'launch_reason', 'screen_reason', 'instructions'].map((k) =>
            r[k] ? (
              <p className={k === 'error' ? 'error-text' : 'note'} key={k}>
                {text(r[k])}
              </p>
            ) : null,
          )}
          <Download
            name={`emulator-${id}.json`}
            content={btoa(unescape(encodeURIComponent(JSON.stringify(r, null, 2))))}
            mime="application/json"
          />
          {r.package && (
            <a className="btn ghost" href={packageLink('inspector', 'lab', id, r.kind)}>
              Certificate Inspector
            </a>
          )}
          {r.kind === 'theme' && r.install === 'installed' && (
            <>
              <p>
                {t(
                  'Open Menu → Settings → Themes → General and apply the theme. Record each screen below; theme UID is never launched.',
                  'Откройте Меню → Параметры → Темы → Общие и примените тему. Отметьте проверенные экраны; UID темы не запускается.',
                )}
              </p>
              <div className="form-row">
                <select
                  aria-label={t('Theme screen', 'Экран темы')}
                  value={step}
                  onChange={(e) => setStep(e.target.value)}
                >
                  {[
                    ['applied', 'Applied', 'Применена'],
                    ['home', 'Home', 'Главный экран'],
                    ['menu', 'Menu', 'Меню'],
                    ['lists', 'Lists', 'Списки'],
                    ['dialogs', 'Dialogs', 'Диалоги'],
                  ].map(([v, en, ru]) => (
                    <option key={v} value={v}>
                      {t(en ?? '', ru ?? '')}
                    </option>
                  ))}
                </select>
                <select
                  aria-label={t('Observation', 'Наблюдение')}
                  value={result}
                  onChange={(e) => setResult(e.target.value)}
                >
                  {['pass', 'fail', 'not-tested', 'unsupported'].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
                <button
                  className="btn secondary"
                  disabled={!ready || action.isPending}
                  onClick={() => action.mutate({ action: 'observe', step, result })}
                >
                  {t('Record & capture', 'Записать и снять экран')}
                </button>
              </div>
            </>
          )}
          <div className="form-row">
            <button
              className="btn secondary"
              disabled={!ready || action.isPending}
              onClick={() => action.mutate({ action: 'shot' })}
            >
              {t('Save screenshot', 'Сохранить снимок')}
            </button>
            <button
              className="btn ghost"
              disabled={!ready || action.isPending}
              onClick={() => action.mutate({ action: 'logs' }, { onSuccess: setLogs })}
            >
              {t('Refresh logs', 'Обновить журнал')}
            </button>
          </div>
          <div className="lab-gallery">
            {r.screenshots?.map((shot) => (
              <Shot key={shot.name} id={id} shot={shot} />
            ))}
          </div>
          <JsonReport
            value={logs ?? r}
            label={t('Events, errors and logs', 'События, ошибки и логи')}
          />
          {['app', 'theme'].includes(r.kind) && r.install === 'installed' && (
            <>
              <h3>{t('Verified → transfer to phone', 'Проверено → передать на телефон')}</h3>
              <p>
                {t(
                  'The same package bytes are checked by SHA-256. Complete installation and testing on Nokia separately.',
                  'Те же байты пакета проверяются по SHA-256. Установку и работу на Nokia проверьте отдельно.',
                )}
              </p>
              <div className="form-row">
                <DeviceSelect value={device} onChange={setDevice} capability="transfer" />
                <Field label={t('Destination path', 'Путь назначения')}>
                  <input value={path} onChange={(e) => setPath(e.target.value)} />
                </Field>
                <button
                  className="btn primary"
                  disabled={!device || confirm.busy}
                  onClick={() =>
                    confirm.ask(
                      t(
                        'Transfer tested package? Complete installation and testing on Nokia.',
                        'Передать проверенный пакет? Завершите установку и проверку на Nokia.',
                      ),
                      'transfer',
                    )
                  }
                >
                  {t('Transfer', 'Передать')}
                </button>
              </div>
            </>
          )}
          {confirm.dialog(async (kind) =>
            action.mutateAsync({
              action: kind,
              id,
              device,
              path: path || r.package?.name || '',
              confirm: true,
            }),
          )}
        </>
      )}
    </Card>
  );
}
function Shot({ id, shot }: { id: string; shot: NonNullable<LabReport['screenshots']>[number] }) {
  const api = useApi(),
    { t } = usePreferences();
  const data = useQuery({
    queryKey: ['lab-shot', id, shot.name],
    queryFn: ({ signal }) =>
      api.request(
        '/api/lab',
        { action: 'saved-shot', id, name: shot.name },
        z.object({ png: z.string() }),
        signal,
      ),
    staleTime: Infinity,
  });
  return data.data ? (
    <a href={'data:image/png;base64,' + data.data.png} download={shot.name}>
      <img
        width="120"
        src={'data:image/png;base64,' + data.data.png}
        alt={`EKA2L1 ${shot.width}×${shot.height} ${shot.at}`}
      />
      {t('Download PNG', 'Скачать PNG')} ↓
    </a>
  ) : (
    <ErrorMessage error={data.error} />
  );
}
