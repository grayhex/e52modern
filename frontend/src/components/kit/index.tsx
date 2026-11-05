import type { LucideIcon } from 'lucide-react';
import { AlertTriangle, CircleCheck, CircleDashed, CircleHelp, CircleX, Ban } from 'lucide-react';
import type { PropsWithChildren, ReactNode } from 'react';
import { usePreferences } from '../../state/app';

/**
 * Nokia Classic UI kit: one set of plain-HTML building blocks styled by `kit.css` from the shared
 * `--nokia-*` tokens (4/8 px spacing, 5–7 px radii). Pages compose these instead of local layouts,
 * so MUI charts, the file browser and legacy screens share one visual language.
 */

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="k-page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="k-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="k-page-actions">{actions}</div>}
    </header>
  );
}

export function SectionPanel({
  title,
  meta,
  actions,
  children,
  className = '',
  id,
}: PropsWithChildren<{
  title?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
  id?: string;
}>) {
  return (
    <section className={`k-panel ${className}`.trim()} {...(id ? { id } : {})}>
      {(title || actions || meta) && (
        <div className="k-panel-head">
          {title && <h2>{title}</h2>}
          {meta && <span className="k-meta">{meta}</span>}
          {actions && <div className="k-panel-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export type Tone = 'ok' | 'warn' | 'bad' | 'unknown' | 'off' | 'info';
const TONE_ICON: Record<Tone, LucideIcon> = {
  ok: CircleCheck,
  warn: AlertTriangle,
  bad: CircleX,
  unknown: CircleHelp,
  off: Ban,
  info: CircleDashed,
};

/** Status is text + icon + border, never colour alone; “not tested” is its own tone, not “bad”. */
export function StatusIndicator({ tone, children }: PropsWithChildren<{ tone: Tone }>) {
  const Icon = TONE_ICON[tone];
  return (
    <span className={`k-status k-status--${tone}`}>
      <Icon size={14} aria-hidden="true" />
      {children}
    </span>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  children,
  actions,
  media,
}: PropsWithChildren<{
  icon?: LucideIcon;
  title: string;
  actions?: ReactNode;
  media?: ReactNode;
}>) {
  return (
    <div className="k-empty" role="status">
      {media ?? (Icon && <Icon size={32} aria-hidden="true" className="k-empty-icon" />)}
      <div className="k-empty-body">
        <h2>{title}</h2>
        {children && <div className="k-empty-text">{children}</div>}
        {actions && <div className="k-actions">{actions}</div>}
      </div>
    </div>
  );
}

export function ErrorState({
  title,
  children,
  actions,
}: PropsWithChildren<{ title?: string; actions?: ReactNode }>) {
  const { t } = usePreferences();
  return (
    <div className="k-error" role="alert">
      <CircleX size={20} aria-hidden="true" />
      <div>
        <strong>{title ?? t('Something went wrong', 'Что-то пошло не так')}</strong>
        {children && <p>{children}</p>}
        {actions && <div className="k-actions">{actions}</div>}
      </div>
    </div>
  );
}

/** One measured value. A missing reading renders nothing here: the caller lists it as “not reported”. */
export function Metric({
  icon: Icon,
  label,
  value,
  note,
  progress,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  note?: string | null;
  progress?: number | null;
}) {
  return (
    <div className="k-metric">
      <Icon size={18} aria-hidden="true" className="k-metric-icon" />
      <div className="k-metric-body">
        <span className="k-metric-label">{label}</span>
        <strong className="k-metric-value">{value}</strong>
        {progress != null && (
          <div
            className="k-bar"
            role="progressbar"
            aria-label={label}
            aria-valuenow={Math.round(progress)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <span
              className={`k-bar-fill k-bar-${Math.min(10, Math.max(0, Math.round(progress / 10)))}`}
            />
          </div>
        )}
        {note && <span className="k-metric-note">{note}</span>}
      </div>
    </div>
  );
}

export function ActionToolbar({ children, label }: PropsWithChildren<{ label?: string }>) {
  return (
    <div className="k-toolbar" role="toolbar" {...(label ? { 'aria-label': label } : {})}>
      {children}
    </div>
  );
}

/** Product picture with an honest caption when it is only an illustration. */
export function DeviceIdentity({
  name,
  subtitle,
  image,
  illustration,
  caption,
  status,
  facts,
  actions,
}: {
  name: string;
  subtitle?: ReactNode;
  image: ReactNode;
  illustration?: boolean;
  caption?: ReactNode;
  status?: ReactNode;
  facts?: { label: string; value: ReactNode; note?: ReactNode }[];
  actions?: ReactNode;
}) {
  return (
    <div className="k-identity">
      <figure className={`k-identity-media ${illustration ? 'is-illustration' : ''}`.trim()}>
        {image}
        {caption && <figcaption>{caption}</figcaption>}
      </figure>
      <div className="k-identity-body">
        {status && <div className="k-identity-status">{status}</div>}
        <h2 className="k-identity-name">{name}</h2>
        {subtitle && <p className="k-subtitle">{subtitle}</p>}
        {facts && facts.length > 0 && (
          <dl className="k-facts">
            {facts.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
                {fact.note && <small>{fact.note}</small>}
              </div>
            ))}
          </dl>
        )}
        {actions}
      </div>
    </div>
  );
}

/** Loading placeholder with the shape of the content to come; reduced-motion safe (no animation then). */
export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="k-skeleton" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className={i === lines - 1 ? 'is-short' : ''} />
      ))}
    </div>
  );
}

/** Neutral S60 handset outline used when a model has no registered artwork (never a real photo). */
export function GenericPhone({
  label,
  width,
  height,
}: {
  label: string;
  width?: number;
  height?: number;
}) {
  return (
    <svg
      className="k-generic-phone"
      width={width}
      height={height}
      viewBox="0 0 120 220"
      role="img"
      aria-label={label}
    >
      <rect x="10" y="6" width="100" height="208" rx="14" className="k-phone-body" />
      <rect x="22" y="26" width="76" height="100" rx="4" className="k-phone-screen" />
      <circle cx="60" cy="150" r="10" className="k-phone-key" />
      {[0, 1, 2].map((row) =>
        [0, 1, 2].map((col) => (
          <rect
            key={`${row}-${col}`}
            x={30 + col * 24}
            y={168 + row * 12}
            width="18"
            height="8"
            rx="3"
            className="k-phone-key"
          />
        )),
      )}
    </svg>
  );
}
