import { useRef, useEffect, useId, type PropsWithChildren } from 'react';
import type { Device } from '../api/contracts';
import { useDevices } from '../api/queries';
import { usePreferences } from '../state/app';
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
// eslint-disable-next-line react-refresh/only-export-components
export function supports(device: Device | undefined, capability: string) {
  if (!device) return false;
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
export function DeviceSelect({
  value,
  onChange,
  capability,
}: {
  value: string;
  onChange: (id: string) => void;
  capability?: string;
}) {
  const { data } = useDevices();
  const id = useId();
  const { t } = usePreferences();
  return (
    <div>
      <label htmlFor={id}>{t('Connection', 'Подключение')}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{t('Select connection', 'Выберите подключение')}</option>
        {data?.devices
          .filter((d) => !capability || supports(d, capability))
          .map((d) => (
            <option key={d.id} value={d.id}>
              {d.name ?? d.model ?? d.id} ·{' '}
              {d.connected ? t('Connected', 'Подключено') : t('Disconnected', 'Отключено')}
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
