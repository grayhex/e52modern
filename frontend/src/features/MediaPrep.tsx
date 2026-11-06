import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ZodType } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { useModels } from '../api/queries';
import { ErrorMessage } from '../components/ui';
import { Download } from '../components/workspace';
import { SectionPanel } from '../components/kit';
import { encode } from '../utils/files';
import ReviveSafety from './ReviveSafety';
import {
  mediaExportSchema,
  mediaJobSchema,
  mediaPresetsSchema,
  mediaSourceSchema,
  safetyPlanSchema,
  simpleSchema,
} from '../api/revive';
import { st } from './statements';

const MAX = 48 * 1024 * 1024;
const OUT: [string, string, string][] = [
  ['exported', 'Exported', 'Экспортировано'],
  ['transferred', 'Transferred', 'Передано'],
  ['played-on-device', 'Played on the device', 'Воспроизведено на устройстве'],
];

/** Prepare for Nokia: convert for a chosen model, export, or copy through the Safety Net. Theoretical presets, said plainly. */
export default function MediaPrep({ device }: { device: string }) {
  const api = useApi();
  const cache = useQueryClient();
  const { t, language } = usePreferences();
  const models = useModels().filter((m) => m.id !== 'nokia-n95-family');
  const [model, setModel] = useState('nokia-e52');
  const [preset, setPreset] = useState('');
  const [rotate, setRotate] = useState(0);
  const [jobId, setJobId] = useState('');
  const [planId, setPlanId] = useState('');
  const [sure, setSure] = useState(false);
  const call = <T,>(body: Record<string, unknown>, schema: ZodType<T>) =>
    api.request('/api/revive', body as never, schema);
  const upload = useMutation({
    mutationFn: async (file: File) => {
      if (file.size > MAX) throw Error(t('Choose a file up to 48 MiB', 'Выберите файл до 48 МиБ'));
      return call(
        { action: 'media-upload', name: file.name, content: await encode(file) },
        mediaSourceSchema,
      );
    },
    onSuccess: () => {
      setJobId('');
      setPlanId('');
      setPreset('');
    },
  });
  const source = upload.data;
  const presets = useQuery({
    queryKey: ['revive', device, 'media-presets', model],
    queryFn: () => call({ action: 'media-presets', model }, mediaPresetsSchema),
    retry: false,
  });
  const choices = source ? (presets.data?.presets[source.kind] ?? []) : [];
  const chosen = preset || choices[0]?.id || '';
  const convert = useMutation({
    mutationFn: () =>
      call(
        { action: 'media-convert', source: source?.id, model, preset: chosen, rotate },
        mediaJobSchema,
      ),
    onSuccess: (job) => setJobId(job.id),
  });
  const job = useQuery({
    queryKey: ['revive', device, 'media-job', jobId],
    queryFn: () => call({ action: 'media-job', job: jobId }, mediaJobSchema),
    enabled: Boolean(jobId),
    refetchInterval: (q) =>
      q.state.data && ['queued', 'running'].includes(q.state.data.state) ? 700 : false,
    retry: false,
  });
  const exp = useMutation({
    mutationFn: () => call({ action: 'media-export', job: jobId }, mediaExportSchema),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['revive', device, 'media-job'] }),
  });
  const plan = useMutation({
    mutationFn: () =>
      call({ action: 'safety-plan', scenario: 'media', device, job: jobId }, safetyPlanSchema),
    onSuccess: (p) => setPlanId(p.id),
  });
  const played = useMutation({
    mutationFn: (result: string) =>
      call({ action: 'media-record', device, job: jobId, result, confirm: true }, simpleSchema),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['revive', device, 'media-job'] }),
  });
  const j = job.data;
  const error =
    upload.error ?? convert.error ?? job.error ?? exp.error ?? plan.error ?? played.error;
  return (
    <SectionPanel title={t('Prepare for Nokia', 'Подготовить для Nokia')} id="media-prep">
      <p className="k-note-line" data-testid="media-statement">
        {st(language, presets.data?.statement)}
      </p>
      <div className="rv-form">
        <label>
          {t('Phone model', 'Модель телефона')}
          <select
            value={model}
            onChange={(e) => {
              setModel(e.target.value);
              setPreset('');
            }}
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('Video, music or picture (up to 48 MiB)', 'Видео, музыка или фото (до 48 МиБ)')}
          <input
            type="file"
            aria-label={t('Media file', 'Медиафайл')}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload.mutate(f);
              e.target.value = '';
            }}
          />
        </label>
      </div>
      {source && (
        <>
          <p data-testid="media-source">
            {source.name} · {source.kind} · {Math.round(source.size / 1024)} KiB
            {source.duration ? ` · ${source.duration.toFixed(1)} s` : ''}
          </p>
          <div className="rv-form">
            <label>
              {t('Preset', 'Предустановка')}
              <select value={chosen} onChange={(e) => setPreset(e.target.value)}>
                {choices.map((p) => (
                  <option key={p.id} value={p.id}>
                    {t(p.title.en, p.title.ru)}
                  </option>
                ))}
              </select>
            </label>
            {source.kind !== 'audio' && (
              <label>
                {t('Rotate', 'Повернуть')}
                <select value={rotate} onChange={(e) => setRotate(Number(e.target.value))}>
                  {[0, 90, 180, 270].map((d) => (
                    <option key={d} value={d}>
                      {d}°
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button
              type="button"
              className="k-btn k-btn--primary"
              disabled={!chosen || convert.isPending}
              onClick={() => convert.mutate()}
            >
              {t('Convert', 'Конвертировать')}
            </button>
          </div>
        </>
      )}
      {error && <ErrorMessage error={error} />}
      {j && (
        <div data-testid="media-job" data-state={j.state}>
          <p role="status">
            {j.state === 'queued'
              ? `${t('Queued', 'В очереди')} #${j.queue_position}`
              : j.state === 'running'
                ? t('Converting…', 'Конвертация…')
                : j.state === 'failed'
                  ? `${t('Failed', 'Ошибка')}: ${j.error ?? ''}`
                  : t('Ready', 'Готово')}
            {' · '}
            {t('estimate', 'оценка')} {Math.round(j.estimate_bytes / 1024)} KiB
          </p>
          {j.preview && (
            <img
              alt={t('Preview', 'Предпросмотр')}
              className="rv-preview"
              src={`data:image/jpeg;base64,${j.preview}`}
            />
          )}
          {j.output && (
            <p data-testid="media-output">
              {j.output.name} · {Math.round(j.output.size / 1024)} KiB ·{' '}
              <span className="rv-hash">{j.output.sha256}</span>
            </p>
          )}
          <ul className="rv-levels" data-testid="media-outcomes">
            {OUT.map(([k, en, ru]) => {
              const v = j.outcomes[k as keyof typeof j.outcomes];
              return (
                <li
                  key={k}
                  className={`rv-chip ${v === true || v === 'pass' ? 'rv-chip--ok' : ''}`}
                  data-outcome={k}
                >
                  {t(en, ru)}: {typeof v === 'boolean' ? (v ? t('yes', 'да') : t('no', 'нет')) : v}
                </li>
              );
            })}
          </ul>
          {j.state === 'done' && (
            <div className="k-toolbar">
              <button
                type="button"
                className="k-btn"
                disabled={exp.isPending}
                onClick={() => exp.mutate()}
              >
                {t('Export file and report', 'Экспорт файла и отчёта')}
              </button>
              <button
                type="button"
                className="k-btn k-btn--primary"
                disabled={!device || plan.isPending}
                onClick={() => plan.mutate()}
              >
                {t(
                  'Plan safe copy to the phone',
                  'Запланировать безопасное копирование на телефон',
                )}
              </button>
              <label className="rv-check">
                <input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
                {t('I tried it on the phone', 'Я проверил это на телефоне')}
              </label>
              {(['pass', 'fail'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  className="k-btn"
                  disabled={!sure || !device || played.isPending}
                  onClick={() => played.mutate(r)}
                >
                  {r === 'pass'
                    ? t('It plays', 'Воспроизводится')
                    : t('It does not play', 'Не воспроизводится')}
                </button>
              ))}
            </div>
          )}
          {exp.data && (
            <p>
              <Download content={exp.data.content} name={exp.data.name} /> ·{' '}
              <Download
                content={exp.data.report}
                name={exp.data.report_name}
                mime="application/json"
              />
            </p>
          )}
        </div>
      )}
      <ReviveSafety device={device} planId={planId} onSelect={setPlanId} />
    </SectionPanel>
  );
}
