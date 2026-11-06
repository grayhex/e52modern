import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { cfwPlanSchema, cfwSourcesSchema } from '../api/cfw';
import { imageSchema } from '../api/firmware';
import { DeviceSelect, ErrorMessage } from '../components/ui';
import { Field } from '../components/workspace';
import { SectionPanel, StatusIndicator } from '../components/kit';
import { encode } from '../utils/files';
import { deviceProfiles } from '../components/deviceProfiles';
import { useDevices } from '../api/queries';

const STATUS_LABELS: Record<string, [string, string]> = {
  review: ['Review exact versions', 'Сверьте точные версии'],
  'matched-static': ['Metadata match', 'Совпадение метаданных'],
  declared: ['Entered by you', 'Введено вами'],
  unknown: ['No data', 'Нет данных'],
  blocked: ['Needs attention', 'Нужно уточнить'],
  indexed: ['Indexed', 'Проиндексировано'],
  'user-confirmed': ['Confirmed by you', 'Подтверждено вами'],
};

export default function CfwPreparation({
  sources,
  images,
}: {
  sources: z.infer<typeof cfwSourcesSchema>['sources'];
  images: z.infer<typeof imageSchema>[];
}) {
  const api = useApi(),
    { t, device, setDevice } = usePreferences();
  const familyProfiles = deviceProfiles.filter((p) => p.s60 === 'Symbian^3');
  const detected = useDevices().data?.devices.find((d) => d.id === device)?.model_profile?.id;
  const [pickedProfile, setProfile] = useState(
    () => new URLSearchParams(location.hash.split('?')[1]).get('profile') ?? '',
  );
  const profile =
    familyProfiles.find((p) => p.id === pickedProfile)?.id ??
    familyProfiles.find((p) => p.id === detected)?.id ??
    familyProfiles[0]?.id ??
    '';
  const [source, setSource] = useState('reborn-n8-e7'),
    [image, setImage] = useState(''),
    [file, setFile] = useState<File | null>(null);
  const [metadata, setMetadata] = useState({
    rm: '',
    version: '',
    product_code: '',
    language: '',
    keyboard: '',
  });
  const [backup, setBackup] = useState(false);
  const selected = sources.find((s) => s.id === source);
  const variant = selected?.variants?.find((v) => v.profile === profile);
  const revision = JSON.stringify([
    device,
    profile,
    source,
    image,
    metadata,
    backup,
    file?.name,
    file?.size,
    file?.lastModified,
  ]);
  const request = useMutation({
    mutationFn: async (_revision: string) => {
      void _revision;
      if (file && file.size > 512 * 1024)
        throw Error(t('VPL limit: 512 KiB', 'Лимит VPL: 512 КиБ'));
      return api.request(
        '/api/firmware',
        {
          action: 'cfw-plan',
          device,
          profile,
          source,
          image,
          declared: metadata,
          backup_confirmed: backup,
          manifest: file ? await encode(file) : '',
        },
        cfwPlanSchema,
      );
    },
  });
  return (
    <SectionPanel
      title={t('N8 / E7 preparation (read-only)', 'Подготовка N8 / E7 (только чтение)')}
      id="cfw-preparation"
    >
      <p className="k-note-line">
        {t(
          'Match the exact RM, firmware and language/keyboard variant before reviewing a package. A VPL is unsigned metadata, not proof of authenticity. This tool cannot flash or install firmware.',
          'Сверьте точные RM, прошивку и языковую сборку/клавиатуру перед исследованием пакета. VPL — неподписанные метаданные, а не подтверждение подлинности. Этот инструмент не прошивает и не устанавливает прошивку.',
        )}
      </p>
      <div className="react-fields">
        <Field label={t('Model profile', 'Профиль модели')}>
          <select
            value={profile}
            onChange={(e) => {
              setProfile(e.target.value);
              request.reset();
            }}
          >
            {deviceProfiles
              .filter((p) => p.s60 === 'Symbian^3')
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.rms.join(', ')}
                </option>
              ))}
          </select>
        </Field>
        <DeviceSelect
          value={device}
          onChange={(id) => {
            setDevice(id);
            request.reset();
          }}
        />
        <Field label={t('Author project', 'Проект автора')}>
          <select
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              request.reset();
            }}
          >
            {sources
              .filter((s) => s.symport[profile] === 'research-only')
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {t(s.title.en, s.title.ru)}
                </option>
              ))}
          </select>
        </Field>
        <Field label={t('Indexed image (optional)', 'Проиндексированный образ (необязательно)')}>
          <select
            value={image}
            onChange={(e) => {
              setImage(e.target.value);
              request.reset();
            }}
          >
            <option value="">—</option>
            {images.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label={t('VPL manifest (optional, 512 KiB)', 'Манифест VPL (необязательно, 512 КиБ)')}
        >
          <input
            type="file"
            accept=".vpl,.xml"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              request.reset();
            }}
          />
        </Field>
        {(['rm', 'version', 'product_code', 'language', 'keyboard'] as const).map((key) => (
          <Field
            key={key}
            label={t(
              {
                rm: 'Package RM',
                version: 'Package firmware version',
                product_code: 'Product code',
                language: 'Package language',
                keyboard: 'E7 hardware keyboard variant',
              }[key],
              {
                rm: 'RM пакета',
                version: 'Версия прошивки пакета',
                product_code: 'Код продукта',
                language: 'Язык пакета',
                keyboard: 'Раскладка аппаратной клавиатуры E7',
              }[key],
            )}
          >
            <input
              maxLength={160}
              value={metadata[key]}
              onChange={(e) => {
                setMetadata({ ...metadata, [key]: e.target.value });
                request.reset();
              }}
            />
          </Field>
        ))}
      </div>
      {variant && (
        <p className="k-note-line">
          {t(
            'Author release label (not stock firmware):',
            'Метка релиза автора (не номер штатной прошивки):',
          )}{' '}
          {variant.version}. {t('Keyboard choices:', 'Варианты клавиатуры:')}{' '}
          {variant.keyboards.join(', ') || '—'}.{' '}
          <a className="k-link" href={variant.download} target="_blank" rel="noopener noreferrer">
            {t('Author download', 'Скачать у автора')}
          </a>
        </p>
      )}
      <p className="k-note-line">
        <a className="k-link" href="#tools/firmware">
          {t(
            'Import your unpacked ZIP / core ROM in Firmware Explorer',
            'Импортировать свой распакованный ZIP / core ROM в Firmware Explorer',
          )}
        </a>
      </p>
      <label>
        <input
          type="checkbox"
          checked={backup}
          onChange={(e) => {
            setBackup(e.target.checked);
            request.reset();
          }}
        />{' '}
        {t(
          'I saved my own backups and recovery information',
          'Я сохранил собственные резервные копии и сведения о восстановлении',
        )}
      </label>
      <div className="k-toolbar">
        <button
          className="k-btn"
          disabled={request.isPending || !selected}
          onClick={() => request.mutate(revision)}
        >
          {t('Analyze preparation (dry run)', 'Проверить подготовку (пробный прогон)')}
        </button>
      </div>
      <ErrorMessage error={request.error} />
      {request.data && request.variables === revision && (
        <div aria-live="polite">
          <p>
            <StatusIndicator tone={request.data.status === 'blocked' ? 'bad' : 'info'}>
              {t(
                'Static preparation only; flashing unavailable',
                'Только статическая подготовка; прошивка недоступна',
              )}
            </StatusIndicator>
          </p>
          <ul className="k-list">
            {request.data.checks.map((c) => (
              <li key={c.code}>
                <StatusIndicator
                  tone={
                    c.status === 'blocked' ? 'bad' : c.status === 'unknown' ? 'unknown' : 'info'
                  }
                >
                  {t(...(STATUS_LABELS[c.status] ?? [c.status, c.status]))}
                </StatusIndicator>{' '}
                {t(c.text.en, c.text.ru)}
              </li>
            ))}
          </ul>
          <a
            className="k-link"
            download="cfw-preparation.json"
            href={
              'data:application/json;charset=utf-8,' +
              encodeURIComponent(JSON.stringify(request.data, null, 2))
            }
          >
            {t('Download JSON report', 'Скачать JSON-отчёт')}
          </a>
        </div>
      )}
    </SectionPanel>
  );
}
