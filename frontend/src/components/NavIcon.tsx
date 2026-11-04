import type { ReactNode } from 'react';
const icons: Record<string, ReactNode> = {
  manager: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="11" y="5" width="23" height="38" rx="4" />
        <path d="M19 10h7M20 38h5" />
        <path d="M7 23h14l3 4h14v13H7z" fill="#FFFFFF" stroke="#FFFFFF" strokeWidth="3" />
        <path d="M9 27h12l3 3h13v9H9z" />
      </g>
    </svg>
  ),
  files: (
    <svg className="asset-icon" aria-hidden="true" viewBox="0 0 48 48">
      <g fill="none" stroke="currentColor" strokeWidth="2.4">
        <path d="M7 14h14l5 5h15v22H7zM11 9h14l4 5h8" />
      </g>
    </svg>
  ),
  ringtone: (
    <svg className="asset-icon" aria-hidden="true" viewBox="0 0 48 48">
      <g fill="none" stroke="currentColor" strokeWidth="2.4">
        <path d="M18 34V11l20-5v23M18 20l20-5M18 34c0 6-11 8-11 2s11-8 11-2M38 29c0 6-11 8-11 2s11-8 11-2" />
      </g>
    </svg>
  ),
  connection: (
    <svg className="asset-icon" aria-hidden="true" viewBox="0 0 48 48">
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M8 17h31m-8-8 8 8-8 8M40 32H9m8-8-8 8 8 8" />
      </g>
    </svg>
  ),
  contacts: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="6" y="9" width="36" height="30" rx="4" />
        <circle cx="18" cy="20" r="4" />
        <path d="M11 32c1-5 4-7 7-7s6 2 7 7M29 19h8M29 25h8M29 31h5" />
      </g>
    </svg>
  ),
  calendar: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="7" y="11" width="34" height="30" rx="4" />
        <path d="M7 20h34M16 7v8M32 7v8M16 28h5M27 28h5M16 35h5" />
      </g>
    </svg>
  ),
  messages: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M9 10h29a4 4 0 0 1 4 4v18a4 4 0 0 1-4 4H20L9 43v-7a4 4 0 0 1-4-4V14a4 4 0 0 1 4-4Z" />
        <path d="M14 20h20M14 27h14" />
      </g>
    </svg>
  ),
  media: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M24 12v24a6 6 0 1 1-4-5.7V17l19-5v19a6 6 0 1 1-4-5.7V7L24 10" />
        <path d="M12 9h7M12 14h7" />
      </g>
    </svg>
  ),
  backups: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="7" y="7" width="34" height="10" rx="2" />
        <rect x="7" y="21" width="34" height="20" rx="3" />
        <path d="M18 31a8 8 0 1 1 4 7M18 25v7h7M34 12h1" />
      </g>
    </svg>
  ),
  catalog: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="7" y="7" width="14" height="14" rx="3" />
        <rect x="27" y="7" width="14" height="14" rx="3" />
        <rect x="7" y="27" width="14" height="14" rx="3" />
        <rect x="27" y="27" width="14" height="14" rx="3" />
        <path d="M34 30v8M30 34h8" />
      </g>
    </svg>
  ),
  installed: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="12" y="4" width="24" height="40" rx="5" />
        <path d="M21 9h6M21 39h6" />
        <rect x="18" y="16" width="5" height="5" rx="1" />
        <rect x="26" y="16" width="5" height="5" rx="1" />
        <rect x="18" y="24" width="5" height="5" rx="1" />
        <rect x="26" y="24" width="5" height="5" rx="1" />
      </g>
    </svg>
  ),
  updates: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M24 6v24m-9-9 9 9 9-9" />
        <path d="M8 34v7h32v-7" />
      </g>
    </svg>
  ),
  inspector: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M24 4 40 10v13c0 10-7 17-16 21C15 40 8 33 8 23V10L24 4Z" />
        <path d="m16 24 6 6 11-12" />
      </g>
    </svg>
  ),
  jailbreak: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path
          d="M21 5h6l1.4 5 4 1.8 4.6-2.5 4 4-2.5 4.6 1.8 4L45 23v6l-5 1.4-1.8 4 2.5 4.6-4 4-4.6-2.5-4 1.8L27 47h-6l-1.4-5-4-1.8-4.6 2.5-4-4 2.5-4.6-1.8-4L3 29v-6l5-1.4 1.8-4L7.3 13l4-4 4.6 2.5 4-1.8Z"
          transform="translate(0 -2) scale(1 .94)"
        />
        <circle cx="24" cy="24" r="7" />
      </g>
    </svg>
  ),
  themes: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M24 5C13 5 5 13 5 24s8 19 19 19c4 0 6-2 6-5 0-2-2-4-2-6 0-3 2-4 5-4h5c4 0 5-3 5-7C43 12 35 5 24 5Z" />
        <circle cx="16" cy="18" r="2" />
        <circle cx="26" cy="14" r="2" />
        <circle cx="34" cy="21" r="2" />
        <circle cx="14" cy="28" r="2" />
      </g>
    </svg>
  ),
  lab: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="5" y="7" width="38" height="29" rx="4" />
        <path d="M18 42h12M24 36v6" />
        <path d="m21 16 11 6-11 6z" />
      </g>
    </svg>
  ),
  apps: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="5" y="8" width="38" height="32" rx="4" />
        <path d="M5 17h38M17 24l-6 5 6 5M31 24l6 5-6 5M27 23l-6 12" />
      </g>
    </svg>
  ),
  device: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="10" y="4" width="22" height="39" rx="4" />
        <path d="M18 9h6M19 38h4" />
        <circle cx="34" cy="32" r="10" fill="#FFFFFF" stroke="#FFFFFF" strokeWidth="3" />
        <circle cx="34" cy="32" r="9" />
        <path d="m30 32 3 3 6-7" />
      </g>
    </svg>
  ),
  overview: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path
          d="M21 5h6l1.4 5 4 1.8 4.6-2.5 4 4-2.5 4.6 1.8 4L45 23v6l-5 1.4-1.8 4 2.5 4.6-4 4-4.6-2.5-4 1.8L27 47h-6l-1.4-5-4-1.8-4.6 2.5-4-4 2.5-4.6-1.8-4L3 29v-6l5-1.4 1.8-4L7.3 13l4-4 4.6 2.5 4-1.8Z"
          transform="translate(0 -2) scale(1 .94)"
        />
        <circle cx="24" cy="24" r="7" />
      </g>
    </svg>
  ),
  activity: (
    <svg
      className="asset-icon"
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 48 48"
    >
      <g
        fill="none"
        stroke="#0F172A"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="5" y="9" width="38" height="30" rx="4" />
        <path d="M10 26h7l4-9 6 17 4-8h7" />
      </g>
    </svg>
  ),
};
export function NavIcon({ name }: { name: string }) {
  return icons[name] ?? null;
}
