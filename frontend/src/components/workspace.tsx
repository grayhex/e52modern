import {
  useEffect,
  useRef,
  useId,
  cloneElement,
  isValidElement,
  type PropsWithChildren,
} from 'react';
import { usePreferences } from '../state/app';
import { ErrorMessage } from './ui';
export function Field({ label, children }: PropsWithChildren<{ label: string }>) {
  const generated = useId();
  const id = isValidElement<{ id?: string }>(children)
    ? (children.props.id ?? generated)
    : generated;
  return (
    <div className="react-field">
      <label htmlFor={id}>{label}</label>
      {isValidElement<{ id?: string }>(children) ? cloneElement(children, { id }) : children}
    </div>
  );
}
export function Download({
  content,
  name,
  mime = 'application/octet-stream',
  auto = false,
}: {
  content: string;
  name: string;
  mime?: string | undefined;
  auto?: boolean;
}) {
  const ref = useRef<HTMLAnchorElement>(null);
  const url = `data:${mime};base64,${content}`;
  const clicked = useRef('');
  const { t } = usePreferences();
  useEffect(() => {
    if (auto && clicked.current !== url) {
      clicked.current = url;
      ref.current?.click();
    }
  }, [url, auto]);
  return (
    <a className="text-link" ref={ref} href={url || undefined} download={name}>
      {t('Download', 'Скачать')} {name} ↓
    </a>
  );
}
export function JsonReport({ value, label }: { value: unknown; label?: string }) {
  const { t } = usePreferences();
  return (
    <details>
      <summary>{label ?? t('Detailed report', 'Подробный отчёт')}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
export function OperationStatus({
  pending,
  error,
  success,
}: {
  pending: boolean;
  error: unknown;
  success?: string;
}) {
  const { t } = usePreferences();
  return (
    <>
      <ErrorMessage error={error} />
      <p role="status">{pending ? t('Working…', 'Выполняется…') : success}</p>
    </>
  );
}
export function Modal({
  title,
  onClose,
  children,
}: PropsWithChildren<{ title: string; onClose: () => void }>) {
  const ref = useRef<HTMLDialogElement>(null),
    { t } = usePreferences();
  useEffect(() => {
    const node = ref.current;
    node?.showModal();
    return () => node?.close();
  }, []);
  return (
    <dialog
      className="react-modal"
      ref={ref}
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="card-head">
        <h2>{title}</h2>
        <button className="btn ghost" autoFocus onClick={onClose}>
          {t('Close', 'Закрыть')}
        </button>
      </div>
      {children}
    </dialog>
  );
}
