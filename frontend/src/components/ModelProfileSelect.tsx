import { deviceProfiles, profileLabel, targetForProfile } from './deviceProfiles';
import { usePreferences } from '../state/app';
import { Field } from './workspace';
import type { Target } from './targets';
export function ModelProfileSelect({
  target,
  onTarget,
}: {
  target: Target;
  onTarget: (target: Target) => void;
}) {
  const { t } = usePreferences();
  const selected =
    deviceProfiles.find(
      (p) => p.target_model === target.model && (p.s60 === 'Symbian^3' || p.symbian === target.os),
    )?.id ?? '';
  return (
    <Field label={t('Model profile', 'Профиль модели')}>
      <select value={selected} onChange={(e) => onTarget(targetForProfile(e.target.value))}>
        <option value="" disabled>
          {t('Custom / unidentified', 'Другая / не определена')}
        </option>
        {deviceProfiles.map((p) => (
          <option key={p.id} value={p.id}>
            {profileLabel(p)}
          </option>
        ))}
      </select>
    </Field>
  );
}
