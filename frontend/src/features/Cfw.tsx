import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import type { ZodType } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { ErrorMessage } from '../components/ui';
import { Download } from '../components/workspace';
import { PageHeader, SectionPanel, StatusIndicator, type Tone } from '../components/kit';
import { encode } from '../utils/files';
import { linkLabel, translate } from './cfwText';
import {
  cfwSourcesSchema,
  eka1Schema,
  imageListSchema,
  inventorySchema,
  scanSchema,
} from '../api/cfw';
import { st } from './statements';

const VERDICT: Record<string, [string, string, Tone]> = {
  'vulnerable-version': ['Vulnerable version (declared)', 'Уязвимая версия (заявлена вами)', 'bad'],
  'suspicious-pattern': ['Suspicious pattern', 'Подозрительный шаблон', 'warn'],
  'no-pattern-found': [
    'No pattern found (not proof of safety)',
    'Шаблонов не найдено (это не доказательство безопасности)',
    'info',
  ],
  unknown: ['Unknown', 'Неизвестно', 'unknown'],
  'not-tested': ['Not tested', 'Не проверялось', 'unknown'],
};
const APPLIES: Record<string, [string, string]> = {
  wizard: ['Revive wizard', 'Мастер Revive'],
  'not-applicable': ['Not applicable', 'Не применимо'],
  'blocked-without-evidence': ['Blocked without evidence', 'Заблокировано без доказательств'],
};

/** Firmwares and modifications: author metadata, read-only inventory, advisory scanner, experimental EKA1 → RPKG. */
export default function Cfw() {
  const api = useApi();
  const { t, language } = usePreferences();
  const tr = (text: string) => translate(language, text);
  const [image, setImage] = useState('');
  const [baseline, setBaseline] = useState('');
  const [declared, setDeclared] = useState({ cfw: '', model: '', version: '' });
  const [picked, setPicked] = useState('');
  const call = <T,>(path: string, body: Record<string, unknown>, schema: ZodType<T>) =>
    api.request(path, body as never, schema);
  const sources = useQuery({
    queryKey: ['cfw', 'sources'],
    queryFn: () => call('/api/firmware', { action: 'cfw-sources' }, cfwSourcesSchema),
  });
  const images = useQuery({
    queryKey: ['cfw', 'images'],
    queryFn: () => call('/api/firmware', { action: 'list' }, imageListSchema),
  });
  const ready = (images.data?.images ?? []).filter((i) => i.status === 'ready');
  const inventory = useMutation({
    mutationFn: () =>
      call(
        '/api/firmware',
        { action: 'cfw-inventory', id: image, ...(baseline ? { baseline } : {}) },
        inventorySchema,
      ),
  });
  const scan = useMutation({
    mutationFn: () =>
      call(
        '/api/firmware',
        { action: 'cfw-scan', id: image, declared: declared.cfw ? declared : null },
        scanSchema,
      ),
  });
  const convert = useMutation({
    mutationFn: async (file: File) => {
      if (file.size > 48 * 1024 * 1024)
        throw Error(t('Choose a ROM dump up to 48 MiB', 'Выберите дамп ROM до 48 МиБ'));
      return call(
        '/api/firmware',
        { action: 'eka1-convert', name: file.name, content: await encode(file) },
        eka1Schema,
      );
    },
  });
  const s = sources.data;
  const error = sources.error ?? images.error ?? inventory.error ?? scan.error ?? convert.error;
  return (
    <>
      <PageHeader
        title={t('Custom firmware', 'Кастомные прошивки')}
        subtitle={t(
          'Read-only research. Nothing here flashes, writes or boots anything, and no file leaves this server.',
          'Только исследование. Здесь ничего не прошивается, не записывается и не загружается, файлы не покидают сервер.',
        )}
      />
      {error && <ErrorMessage error={error} />}
      <SectionPanel
        title={t('Sources (author metadata only)', 'Источники (только данные авторов)')}
        id="cfw-sources"
      >
        <p className="k-note-line">{tr(s?.note ?? '')}</p>
        <ul className="rv-ops">
          {s?.sources.map((src) => (
            <li key={src.id} className="rv-op" data-source={src.id}>
              <div className="rv-op-head">
                <strong>{t(src.title.en, src.title.ru)}</strong>
                <StatusIndicator tone="info">{src.platform}</StatusIndicator>
              </div>
              <dl className="rv-op-meta">
                <div>
                  <dt>{t('Kind', 'Тип')}</dt>
                  <dd>{tr(src.kind)}</dd>
                </div>
                <div>
                  <dt>{t('Version / date', 'Версия / дата')}</dt>
                  <dd>
                    {tr(src.release.version)} / {tr(src.release.date)}
                  </dd>
                </div>
                <div>
                  <dt>{t('Models (RM)', 'Модели (RM)')}</dt>
                  <dd>{src.models.map((m) => `${m.name} (${tr(m.rm)})`).join('; ')}</dd>
                </div>
                <div>
                  <dt>{t('Distribution', 'Распространение')}</dt>
                  <dd>{tr(src.distribution)}</dd>
                </div>
              </dl>
              <p className="k-note-line">
                {Object.entries(src.links).map(([k, v]) =>
                  v.startsWith('http') && !v.includes(' ') ? (
                    <a
                      key={k}
                      className="k-link"
                      href={v}
                      rel="noreferrer noopener"
                      target="_blank"
                    >
                      {linkLabel(language, k)}{' '}
                    </a>
                  ) : (
                    <span key={k}>
                      {k}: {v}{' '}
                    </span>
                  ),
                )}
              </p>
              <ul>
                {src.limitations.map((l) => (
                  <li key={l}>{tr(l)}</li>
                ))}
              </ul>
              <ul className="rv-levels">
                {Object.entries(src.symport).map(([m, v]) => (
                  <li key={m} className="rv-chip" data-applies={`${src.id}:${m}`}>
                    {m}: {t(...(APPLIES[v] ?? [v, v]))}
                  </li>
                ))}
              </ul>
              {src.advisories.map((id) => {
                const adv = s.advisories[id];
                return adv ? (
                  <div key={id} className="rv-high-risk" role="note" data-warning={id}>
                    <StatusIndicator tone="warn">
                      {t('Before you install: advisory', 'Перед установкой: уведомление')} {id}
                    </StatusIndicator>
                    <p>
                      {tr(adv.title)}. {t('Published', 'Опубликовано')} {adv.published}; CVSS{' '}
                      {adv.severity.cvss_v3_1} {adv.severity.rating} ({adv.severity.scored_by}).{' '}
                      {tr(adv.platform)}
                    </p>
                    <p className="k-note-line">{tr(adv.severity.author_claim)}</p>
                    <ul>
                      {adv.sources.map((x) => (
                        <li key={x.url}>
                          <a
                            className="k-link"
                            href={x.url}
                            rel="noreferrer noopener"
                            target="_blank"
                          >
                            {tr(x.label)}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null;
              })}
            </li>
          ))}
        </ul>
        <h3>{t('Containers', 'Контейнеры')}</h3>
        <ul className="k-list" data-testid="cfw-containers">
          {Object.entries(s?.containers ?? {}).map(([k, v]) => (
            <li key={k}>
              <span>{k}</span>
              <span>{tr(v)}</span>
            </li>
          ))}
        </ul>
      </SectionPanel>

      <SectionPanel
        title={t('Analyse an image you uploaded', 'Анализ загруженного образа')}
        id="cfw-analyse"
      >
        <p className="k-note-line">
          {t(
            'Upload images in the Firmware & ROM Explorer (Tools). Only your own images appear here.',
            'Образы загружаются в Firmware & ROM Explorer (Инструменты). Здесь только ваши образы.',
          )}
        </p>
        <div className="rv-form">
          <label>
            {t('Image', 'Образ')}
            <select value={image} onChange={(e) => setImage(e.target.value)}>
              <option value="">—</option>
              {ready.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name} ({i.kind})
                </option>
              ))}
            </select>
          </label>
          <label>
            {t('Baseline image (optional)', 'Базовый образ (необязательно)')}
            <select value={baseline} onChange={(e) => setBaseline(e.target.value)}>
              <option value="">—</option>
              {ready
                .filter((i) => i.id !== image)
                .map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name}
                  </option>
                ))}
            </select>
          </label>
          <button
            type="button"
            className="k-btn"
            disabled={!image || inventory.isPending}
            onClick={() => inventory.mutate()}
          >
            {t('Inventory of potential modifications', 'Инвентарь возможных модификаций')}
          </button>
          <h4>
            {t(
              'Security scan (declare what you believe it is)',
              'Проверка безопасности (укажите, что это, по-вашему)',
            )}
          </h4>
          <label>
            CFW
            <input
              value={declared.cfw}
              placeholder="delight"
              maxLength={40}
              onChange={(e) => setDeclared({ ...declared, cfw: e.target.value })}
            />
          </label>
          <label>
            {t('Model', 'Модель')}
            <input
              value={declared.model}
              placeholder="Nokia N8"
              maxLength={40}
              onChange={(e) => setDeclared({ ...declared, model: e.target.value })}
            />
          </label>
          <label>
            {t('Version', 'Версия')}
            <input
              value={declared.version}
              placeholder="6.7"
              maxLength={40}
              onChange={(e) => setDeclared({ ...declared, version: e.target.value })}
            />
          </label>
          <button
            type="button"
            className="k-btn k-btn--primary"
            disabled={!image || scan.isPending}
            onClick={() => scan.mutate()}
          >
            {t('Scan for known patterns', 'Искать известные шаблоны')}
          </button>
        </div>
        {inventory.data && (
          <ul className="k-list" data-testid="cfw-inventory">
            {Object.entries(inventory.data.categories).map(([k, v]) => (
              <li key={k} data-category={k}>
                <span>
                  <strong>{k}</strong> ({v.items.length})<br />
                  <small>{v.basis}</small>
                </span>
                <span>
                  {v.items
                    .slice(0, 3)
                    .map((i) => i.url ?? i.path)
                    .join(', ')}
                </span>
              </li>
            ))}
          </ul>
        )}
        {scan.data && (
          <div data-testid="cfw-scan" data-verdict={scan.data.verdict}>
            <p role="status">
              <StatusIndicator tone={VERDICT[scan.data.verdict]?.[2] ?? 'unknown'}>
                {t(VERDICT[scan.data.verdict]?.[0] ?? '', VERDICT[scan.data.verdict]?.[1] ?? '')}
              </StatusIndicator>{' '}
              {t('Files scanned', 'Просканировано файлов')}: {scan.data.coverage.files_scanned};{' '}
              {t('not tested', 'не проверено')}: {scan.data.coverage.not_tested_total}; DB{' '}
              {scan.data.db_version}
            </p>
            <ul className="k-list">
              {scan.data.findings.map((f, i) => (
                <li key={i}>
                  <span>
                    {f.title}
                    <br />
                    <small>
                      {f.path} · {f.sha256.slice(0, 12)}… · @{f.offset}
                    </small>
                  </span>
                  <span>{f.status}</span>
                </li>
              ))}
            </ul>
            <p className="k-note-line">{st(language, scan.data.statement)}</p>
          </div>
        )}
      </SectionPanel>

      <SectionPanel
        title={t('EKA1 ROM → RPKG (experimental)', 'ROM EKA1 → RPKG (экспериментально)')}
        id="cfw-eka1"
      >
        <p className="k-note-line">
          {t(
            'For old EKA1 ROM dumps you own (base 0x50000000). Not for the E52/E72/N95 (EKA2). It converts a file structure: it does not boot or emulate anything.',
            'Для ваших дампов старых ROM EKA1 (база 0x50000000). Не для E52/E72/N95 (EKA2). Конвертируется структура файлов: ничего не загружается и не эмулируется.',
          )}
        </p>
        <label className="rv-form">
          {t('ROM dump (up to 48 MiB)', 'Дамп ROM (до 48 МиБ)')}
          <input
            type="file"
            aria-label={t('EKA1 ROM dump', 'Дамп ROM EKA1')}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                setPicked(f.name);
                convert.mutate(f);
              }
              e.target.value = '';
            }}
          />
        </label>
        {convert.data && (
          <div data-testid="eka1-result" data-status={convert.data.report.status}>
            <p role="status">
              {picked}:{' '}
              <StatusIndicator tone={convert.data.report.status === 'converted' ? 'info' : 'off'}>
                {convert.data.report.status}
              </StatusIndicator>{' '}
              {convert.data.report.reason ?? ''} · accepted-by-emulator:{' '}
              {convert.data.report.accepted_by_emulator} · booted: {convert.data.report.booted} ·{' '}
              {t('real image tested', 'проверено на реальном образе')}:{' '}
              {String(convert.data.report.real_image_tested)}
            </p>
            {convert.data.rpkg_name && (
              <p>
                <Download content={convert.data.rpkg} name={convert.data.rpkg_name} />
              </p>
            )}
            <p>
              <Download
                content={convert.data.report_json}
                name={convert.data.report_name}
                mime="application/json"
              />
            </p>
          </div>
        )}
      </SectionPanel>
    </>
  );
}
