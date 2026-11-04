import { usePreferences } from '../state/app';
import { Field } from './workspace';
import { useFirmwareImages } from '../hooks/useFirmwareImages';

import type { Target } from './targets';

export function TargetFields({
  target,
  onTarget,
  firmwareId,
  onFirmware,
}: {
  target: Target;
  onTarget: (value: Target) => void;
  firmwareId: string;
  onFirmware: (value: string) => void;
}) {
  const { t } = usePreferences();
  const images = useFirmwareImages();
  const ready = images.data?.images.filter((image) => image.status === 'ready') ?? [];
  return (
    <div className="react-fields">
      {(
        [
          ['model', 'Model', 'Модель'],
          ['rm', 'RM', 'RM'],
          ['firmware', 'Firmware', 'Прошивка'],
          ['os', 'Symbian', 'Symbian'],
        ] as const
      ).map(([key, en, ru]) => (
        <Field label={t(en, ru)} key={key}>
          <input
            value={target[key]}
            onChange={(e) => onTarget({ ...target, [key]: e.target.value })}
          />
        </Field>
      ))}
      <Field label={t('Firmware image (optional)', 'Образ прошивки (необязательно)')}>
        <select value={firmwareId} onChange={(e) => onFirmware(e.target.value)}>
          <option value="">
            {t('None — system DLLs stay unknown', 'Нет — системные DLL остаются неизвестными')}
          </option>
          {ready.map((image) => (
            <option key={image.id} value={image.id}>
              {image.label || image.name}
            </option>
          ))}
        </select>
      </Field>
    </div>
  );
}

export function RuntimeFiles({
  files,
  onFiles,
}: {
  files: File[];
  onFiles: (files: File[]) => void;
}) {
  const { t } = usePreferences();
  return (
    <div className="react-fields">
      <Field
        label={t(
          'Runtime packages you supply (SIS/SISX, up to 12)',
          'Runtime-пакеты, которые вы предоставляете (SIS/SISX, до 12)',
        )}
      >
        <input
          type="file"
          multiple
          accept=".sis,.sisx"
          onChange={(e) => onFiles(Array.from(e.target.files ?? []).slice(0, 12))}
        />
      </Field>
      {files.length > 0 && (
        <ul className="note">
          {files.map((file) => (
            <li key={file.name}>
              {file.name} · {Math.ceil(file.size / 1024)} KiB
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
