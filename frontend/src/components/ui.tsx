import { useRef, useEffect, useId, type PropsWithChildren } from 'react';
import type { Device } from '../api/contracts';
import { useDevices } from '../api/queries';
import { usePreferences } from '../state/app';
import { STATUS_TEXT, blockedReason, unverifiedReason } from '../api/capabilities';
export function Card({ children, className = '' }: PropsWithChildren<{ className?: string }>) {
  return <section className={`card ${className}`}>{children}</section>;
}
export function ErrorMessage({ error }: { error: unknown }) {
  return error ? (
    <p className="error-text" role="alert">
      {error instanceof Error ? error.message : 'Request failed'}
    </p>
  ) : null;
}
export function Reading({ value }: { value: string | number | null | undefined }) {
  const { t } = usePreferences();
  return value === null ||
    value === undefined ||
    /^(unknown|unavailable|unsupported|none|null|n\/a|undefined)?$/i.test(String(value).trim()) ? (
    <span className="device-value value-state--unknown">ⓘ {t('No data', 'Нет данных')}</span>
  ) : (
    <span>{value}</span>
  );
}
/** Operation (UI vocabulary) → capability-matrix operations that can serve it. */
const MATRIX_OPS: Record<string, string[]> = {
  list: ['files.list'],
  download: ['files.download'],
  upload: ['files.upload', 'files.stage'],
  mkdir: ['files.mkdir'],
  delete: ['files.delete'],
  backup: ['files.list', 'files.download'],
  files: ['files.list'],
  transfer: ['packages.transfer', 'packages.opp-push'],
  'opp-push': ['packages.opp-push'],
  'media-read': ['media.read'],
  'device-details': ['identity.read'],
  'personal-data': ['contacts.read', 'calendar.read', 'tasks.read', 'sms.read'],
};
// eslint-disable-next-line react-refresh/only-export-components
export function supports(device: Device | undefined, capability: string) {
  if (!device) return false;
  // The capability matrix is the source of truth; a blocked operation is never offered.
  const ops = MATRIX_OPS[capability];
  if (device.capability_matrix && ops)
    return ops.some((op) => {
      const state = device.capability_matrix?.[op];
      return state !== undefined && state.attempt !== 'blocked';
    });
  if (device.capabilities.includes(capability)) return true;
  const aliases: Record<string, string> = {
    list: 'files-list',
    download: 'files-download',
    backup: 'files-backup',
    upload: 'files-upload',
    mkdir: 'files-mkdir',
    delete: 'files-delete',
  };
  if (aliases[capability] && device.capabilities.includes(aliases[capability])) return true;
  if (capability === 'upload' && device.capabilities.includes('files-stage')) return true;
  return (
    !['obexftp', 'obex-opp'].includes(device.transport) &&
    device.capabilities.includes('files') &&
    ['list', 'download', 'upload', 'mkdir', 'delete', 'backup'].includes(capability)
  );
}
/** Why the chosen connection cannot do this; renders nothing when the operation may be tried. */
export function CapabilityHint({
  device,
  ops,
  verified = false,
}: {
  device: Device | undefined;
  ops: string[];
  /** Require a successful probe instead of merely “may be tried”. */
  verified?: boolean;
}) {
  const { t } = usePreferences();
  const reason = verified ? unverifiedReason(device, ops[0] ?? '') : blockedReason(device, ...ops);
  if (!device || !reason) return null;
  const [en, ru] = STATUS_TEXT[reason.status];
  return (
    <p className="capability-hint" role="status">
      <strong>{t(en, ru)}:</strong> {reason.evidence}.{' '}
      <a href="#phone/connection">{t('Connection details', 'Сведения о подключении')}</a>
    </p>
  );
}
export function DeviceSelect({
  value,
  onChange,
  capability,
  label,
}: {
  value: string;
  onChange: (id: string) => void;
  capability?: string;
  label?: string;
}) {
  const { data } = useDevices();
  const id = useId();
  const { t } = usePreferences();
  return (
    <div>
      <label htmlFor={id}>{label ?? t('Connection', 'Подключение')}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{t('Select connection', 'Выберите подключение')}</option>
        {data?.devices
          .filter((d) => !capability || supports(d, capability))
          .map((d) => (
            <option key={d.id} value={d.id}>
              {(d.model_profile
                ? t(d.model_profile.name, d.model_profile.name_ru ?? d.model_profile.name)
                : undefined) ??
                d.name ??
                d.model ??
                d.id}{' '}
              · {d.connected ? t('Connected', 'Подключено') : t('Disconnected', 'Отключено')}
            </option>
          ))}
      </select>
    </div>
  );
}
export function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
  busy = false,
  error,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
  error?: unknown;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const { t } = usePreferences();
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
      aria-labelledby="confirmation-title"
    >
      <h2 id="confirmation-title">{t('Confirm operation', 'Подтвердите действие')}</h2>
      <p>{message}</p>
      <ErrorMessage error={error} />
      <div className="form-row">
        <button disabled={busy} onClick={onCancel} className="btn secondary" autoFocus>
          {t('Cancel', 'Отмена')}
        </button>
        <button disabled={busy || Boolean(error)} onClick={onConfirm} className="btn primary">
          {t('Confirm', 'Подтвердить')}
        </button>
      </div>
    </dialog>
  );
}
