import { bytes } from '../utils/files';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import WaveSurfer from 'wavesurfer.js';
import Regions from 'wavesurfer.js/dist/plugins/regions.esm.js';
import { type z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { useDevices } from '../api/queries';
import { audioSourceSchema, audioOutputSchema, objectSchema, text } from '../api/workspace';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
import { Field } from '../components/workspace';
type Source = z.infer<typeof audioSourceSchema>;
type Output = z.infer<typeof audioOutputSchema>;
type Options = {
  start: number;
  end: number;
  mono: boolean;
  normalize: boolean;
  lufs: number;
  fade_in: number;
  fade_out: number;
  bitrate: number;
  sample_rate: number;
};
const initial: Options = {
  start: 0,
  end: 30,
  mono: true,
  normalize: true,
  lufs: -16,
  fade_in: 0.1,
  fade_out: 0.3,
  bitrate: 128,
  sample_rate: 44100,
};
function Waveform({
  source,
  options,
  onRange,
  loop,
}: {
  source: Source;
  options: Options;
  onRange: (start: number, end: number) => void;
  loop: boolean;
}) {
  const api = useApi(),
    { t } = usePreferences(),
    host = useRef<HTMLDivElement>(null),
    wave = useRef<WaveSurfer | null>(null),
    region = useRef<ReturnType<ReturnType<typeof Regions.create>['addRegion']> | null>(null),
    loopRef = useRef(loop),
    rangeRef = useRef({ start: options.start, end: options.end }),
    [error, setError] = useState<unknown>(null),
    [ready, setReady] = useState(false);
  useEffect(() => {
    rangeRef.current = { start: options.start, end: options.end };
  }, [options.start, options.end]);
  useEffect(() => {
    loopRef.current = loop;
  }, [loop]);
  useEffect(() => {
    if (!host.current) return;
    let cancelled = false;
    const regions = Regions.create(),
      instance = WaveSurfer.create({
        container: host.current,
        cspNonce: api.styleNonce,
        waveColor: '#74b8cb',
        progressColor: '#0e74e9',
        cursorColor: '#eab308',
        height: 100,
        minPxPerSec: 40,
        normalize: true,
        plugins: [regions],
      });
    wave.current = instance;
    const offError = instance.on('error', (e) => {
      if (!cancelled) setError(e);
    });
    void instance
      .load(source.preview)
      .then(() => {
        if (cancelled) return;
        region.current = regions.addRegion({
          start: rangeRef.current.start,
          end: rangeRef.current.end,
          color: 'rgba(34,211,238,.22)',
          drag: true,
          resize: true,
          minLength: 0.1,
          maxLength: 180,
        });
        setReady(true);
      })
      .catch((e) => {
        if (!cancelled) setError(e);
      });
    const offUpdate = regions.on('region-updated', (r) => onRange(r.start, r.end));
    const offTime = instance.on('timeupdate', (time) => {
      if (region.current && time >= region.current.end) {
        if (loopRef.current && instance.isPlaying()) instance.setTime(region.current.start);
        else instance.pause();
      }
    });
    const offFinish = instance.on('finish', () => {
      if (region.current && loopRef.current) {
        instance.setTime(region.current.start);
        void instance.play().catch(setError);
      }
    });
    return () => {
      cancelled = true;
      offError();
      offUpdate();
      offTime();
      offFinish();
      instance.destroy();
      wave.current = null;
      region.current = null;
    };
  }, [source, api, onRange]);
  useEffect(() => {
    if (
      ready &&
      region.current &&
      (Math.abs(region.current.start - options.start) > 0.001 ||
        Math.abs(region.current.end - options.end) > 0.001)
    )
      region.current.setOptions({ start: options.start, end: options.end });
  }, [options.start, options.end, ready]);
  return (
    <>
      <div ref={host} aria-label={t('Audio waveform', 'Звуковая волна')} />
      <div className="form-row">
        <button
          className="btn secondary"
          disabled={!ready}
          onClick={() => {
            wave.current?.setTime(options.start);
            void wave.current?.play().catch(setError);
          }}
        >
          {t('Play fragment', 'Слушать фрагмент')}
        </button>
        <button className="btn ghost" onClick={() => wave.current?.pause()}>
          {t('Pause', 'Пауза')}
        </button>
        <Field label={t('Zoom', 'Масштаб')}>
          <input
            type="range"
            min="10"
            max="300"
            defaultValue="40"
            onChange={(e) => wave.current?.zoom(Number(e.target.value))}
          />
        </Field>
      </div>
      <ErrorMessage error={error} />
    </>
  );
}
export default function Ringtone() {
  const api = useApi(),
    { t, device, setDevice } = usePreferences(),
    devices = useDevices(),
    phone = devices.data?.devices.find((d) => d.id === device),
    opp = phone?.capabilities.includes('opp-push');
  const [file, setFile] = useState<File | null>(null),
    [source, setSource] = useState<Source | null>(null),
    [output, setOutput] = useState<Output | null>(null),
    [options, setOptions] = useState(initial),
    [loop, setLoop] = useState(true),
    [path, setPath] = useState(''),
    [message, setMessage] = useState('');
  const confirm = useConfirmedAction<Output>();
  const load = useMutation({
    mutationFn: async () => {
      if (file && (!file.size || file.size > 64 * 1024 ** 2))
        throw Error(t('Choose audio up to 64 MiB', 'Выберите аудио до 64 МиБ'));
      const params = new URLSearchParams(location.hash.split('?')[1]);
      if (source)
        await api.request('/api/ringtone', { action: 'delete', id: source.id }, objectSchema);
      setSource(null);
      setOutput(null);
      const result = file
        ? file.size > 64 * 1024 ** 2
          ? Promise.reject(Error(t('Choose audio up to 64 MiB', 'Выберите аудио до 64 МиБ')))
          : api.upload('/api/ringtone/upload', file, audioSourceSchema)
        : api.request(
            '/api/ringtone',
            {
              action: 'gallery',
              device: params.get('device') ?? '',
              path: params.get('path') ?? '',
              revision: params.get('revision') ?? '',
            },
            audioSourceSchema,
          );
      const r = await result;
      setSource(r);
      setOptions({
        ...initial,
        end: Math.min(30, r.duration),
        fade_in: Math.min(0.1, r.duration / 2),
        fade_out: Math.min(0.3, r.duration / 2),
      });
    },
  });
  const clear = useMutation({
    mutationFn: async () => {
      if (source)
        await api.request('/api/ringtone', { action: 'delete', id: source.id }, objectSchema);
      setSource(null);
      setOutput(null);
    },
  });
  const render = useMutation({
    mutationFn: async () => {
      setOutput(null);
      if (!source) throw Error('Select audio');
      const result = await api.request(
        '/api/ringtone',
        { action: 'export', id: source.id, ...options },
        audioOutputSchema,
      );
      setOutput(result);
    },
  });
  const range = useCallback((start: number, end: number) => {
    setOptions((o) => ({ ...o, start, end }));
    setOutput(null);
  }, []);
  function change(patch: Partial<Options>) {
    setOptions((o) => ({ ...o, ...patch }));
    setOutput(null);
  }
  const busy = load.isPending || render.isPending || clear.isPending || confirm.busy,
    valid =
      !!source &&
      options.start >= 0 &&
      options.end <= source.duration &&
      options.end - options.start >= 0.1 &&
      options.end - options.start <= 180;
  const gallery = !!new URLSearchParams(location.hash.split('?')[1]).get('revision');
  return (
    <>
      <h1>Ringtone Studio</h1>
      <Card>
        <div className="form-row">
          <Field label={t('Audio or video', 'Аудио или видео')}>
            <input
              type="file"
              accept="audio/*,video/*,.m4a,.mp4"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </Field>
          <button
            className="btn primary"
            disabled={busy || (!file && !gallery)}
            onClick={() => load.mutate()}
          >
            {file
              ? t('Open audio', 'Открыть аудио')
              : t('Open gallery file', 'Открыть файл галереи')}
          </button>
          <button className="btn ghost" disabled={!source || busy} onClick={() => clear.mutate()}>
            {t('Clear', 'Очистить')}
          </button>
        </div>
        <p className="muted">
          {t(
            'Processed locally. Files stay in your SymPort environment.',
            'Обработка выполняется локально. Файлы остаются в вашей среде SymPort.',
          )}
        </p>
        <ErrorMessage error={load.error ?? clear.error ?? render.error} />
      </Card>
      <div className="react-ringtone-workspace">
        {source && (
          <Card>
            <fieldset disabled={busy} className="react-editor">
              <Waveform source={source} options={options} onRange={range} loop={loop} />
              <div className="form-row">
                <Field label={t('Preset', 'Пресет')}>
                  <select
                    defaultValue="ringtone"
                    onChange={(e) => {
                      const n = e.target.value === 'notification',
                        duration = n ? 5 : 30,
                        start = Math.min(options.start, Math.max(0, source.duration - duration));
                      change({
                        ...initial,
                        start,
                        end: Math.min(source.duration, start + duration),
                        bitrate: n ? 96 : 128,
                      });
                    }}
                  >
                    <option value="ringtone">{t('Ringtone · 30 s', 'Рингтон · 30 с')}</option>
                    <option value="notification">
                      {t('Notification · 5 s', 'Уведомление · 5 с')}
                    </option>
                  </select>
                </Field>
                {(['start', 'end'] as const).map((k) => (
                  <Field
                    key={k}
                    label={k === 'start' ? t('Start, s', 'Начало, с') : t('End, s', 'Конец, с')}
                  >
                    <input
                      className="react-number"
                      type="number"
                      step=".01"
                      min="0"
                      max={source.duration}
                      value={options[k]}
                      onChange={(e) => change({ [k]: Number(e.target.value) })}
                    />
                  </Field>
                ))}
                <label>
                  <input
                    type="checkbox"
                    checked={loop}
                    onChange={(e) => setLoop(e.target.checked)}
                  />
                  {t('Loop', 'Повтор')}
                </label>
              </div>
              <details>
                <summary>{t('Audio settings', 'Настройки звука')}</summary>
                <div className="react-fields">
                  {(['mono', 'normalize'] as const).map((k) => (
                    <label key={k}>
                      <input
                        type="checkbox"
                        checked={options[k]}
                        onChange={(e) => change({ [k]: e.target.checked })}
                      />
                      {k === 'mono' ? 'Mono' : t('Normalize LUFS', 'Нормализация LUFS')}
                    </label>
                  ))}
                  {(['lufs', 'fade_in', 'fade_out'] as const).map((k) => (
                    <Field
                      label={k === 'lufs' ? 'LUFS' : k === 'fade_in' ? 'Fade In, s' : 'Fade Out, s'}
                      key={k}
                    >
                      <input
                        className="react-number"
                        type="number"
                        step=".1"
                        value={options[k]}
                        onChange={(e) => change({ [k]: Number(e.target.value) })}
                      />
                    </Field>
                  ))}
                  <Field label={t('Bitrate, kbps', 'Битрейт, кбит/с')}>
                    <select
                      value={options.bitrate}
                      onChange={(e) => change({ bitrate: Number(e.target.value) })}
                    >
                      {[64, 96, 128, 160, 192, 256, 320].map((n) => (
                        <option key={n}>{n}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label={t('Sample rate, Hz', 'Частота, Гц')}>
                    <select
                      value={options.sample_rate}
                      onChange={(e) => change({ sample_rate: Number(e.target.value) })}
                    >
                      {[22050, 32000, 44100, 48000].map((n) => (
                        <option key={n}>{n}</option>
                      ))}
                    </select>
                  </Field>
                </div>
              </details>
              <div className="form-row">
                <button
                  className="btn primary"
                  disabled={!valid || busy}
                  onClick={() => render.mutate()}
                >
                  {t('Create MP3', 'Создать MP3')}
                </button>
                <span>
                  {(options.end - options.start).toFixed(2)} / {source.duration.toFixed(2)} s
                </span>
              </div>
            </fieldset>
          </Card>
        )}
        {output && (
          <Card className="react-ringtone-result">
            <h2>{t('Processed MP3', 'Готовый MP3')}</h2>
            <audio controls src={output.url} preload="metadata" />
            <p>
              {output.duration.toFixed(2)} s · {bytes(output.size)} · {output.channels} ch ·{' '}
              {output.sample_rate} Hz
            </p>
            <div className="form-row">
              <a
                className="btn secondary"
                href={output.url + '?download=1'}
                download="SymPort-ringtone.mp3"
              >
                {t('Download MP3', 'Скачать MP3')}
              </a>
              <DeviceSelect value={device} onChange={setDevice} capability="transfer" />
              <Field label={t('Destination', 'Назначение')}>
                <input
                  disabled={!!opp}
                  value={opp ? '' : path}
                  onChange={(e) => setPath(e.target.value)}
                />
              </Field>
              <button
                className="btn primary"
                disabled={!device || !phone?.capabilities.includes('transfer') || busy}
                onClick={() =>
                  confirm.ask(
                    t(
                      'Transfer this processed ringtone to Nokia? Assign it in phone settings after transfer.',
                      'Передать готовый рингтон на Nokia? После передачи назначьте его в настройках телефона.',
                    ),
                    output,
                  )
                }
              >
                {t('Send to Nokia', 'Отправить на Nokia')}
              </button>
            </div>
          </Card>
        )}
      </div>
      <p role="status">{busy ? t('Processing…', 'Обработка…') : message}</p>
      {confirm.dialog(async (result) => {
        const r = await api.request(
          '/api/ringtone',
          {
            action: 'transfer',
            id: result.id,
            version: result.version,
            device,
            path: opp ? '' : path,
            confirm: true,
          },
          objectSchema,
        );
        setMessage(`${text(r.status)} · ${text(r.destination)}`);
      })}
      <ErrorMessage error={confirm.error} />
    </>
  );
}
