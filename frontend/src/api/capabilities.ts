import type { CapabilityState, Device } from './contracts';

/** Operations in display order, grouped by service. Labels are shown through `t(en, ru)`. */
export const SERVICES: { id: string; en: string; ru: string; ops: [string, string, string][] }[] = [
  {
    id: 'identity',
    en: 'Identity and status',
    ru: 'Идентификация и состояние',
    ops: [
      ['identity.read', 'Model, RM, firmware', 'Модель, RM, прошивка'],
      ['telemetry.read', 'Battery and signal', 'Батарея и сигнал'],
      ['storage.read', 'Storage counters', 'Счётчики памяти'],
    ],
  },
  {
    id: 'files',
    en: 'Files and packages',
    ru: 'Файлы и пакеты',
    ops: [
      ['files.list', 'Browse folders', 'Просмотр папок'],
      ['files.download', 'Download files', 'Скачивание файлов'],
      ['files.upload', 'Upload files', 'Загрузка файлов'],
      ['files.stage', 'Staged upload (OBEX)', 'Поэтапная загрузка (OBEX)'],
      ['files.mkdir', 'Create folder', 'Создание папки'],
      ['files.delete', 'Delete', 'Удаление'],
      ['media.read', 'Gallery and streaming', 'Галерея и потоковое чтение'],
      ['packages.transfer', 'Package transfer', 'Передача пакетов'],
      ['packages.opp-push', 'Bluetooth OPP push', 'Отправка по Bluetooth OPP'],
    ],
  },
  {
    id: 'personal',
    en: 'Personal data',
    ru: 'Личные данные',
    ops: [
      ['contacts.read', 'Read contacts', 'Чтение контактов'],
      ['contacts.write', 'Write contacts', 'Запись контактов'],
      ['contacts.stage', 'Stage vCard file', 'vCard-файл на карту'],
      ['calendar.read', 'Read calendar', 'Чтение календаря'],
      ['tasks.read', 'Read tasks', 'Чтение задач'],
      ['sms.read', 'Read SMS', 'Чтение SMS'],
      ['sms.send', 'Send SMS', 'Отправка SMS'],
    ],
  },
  {
    id: 'software',
    en: 'Installed software',
    ru: 'Установленное ПО',
    ops: [
      ['apps.registry', 'Installed applications', 'Установленные приложения'],
      ['install.run', 'Installation', 'Установка'],
    ],
  },
];

export const STATUS_TEXT: Record<CapabilityState['status'], [string, string]> = {
  available: ['Verified', 'Проверено'],
  'not-tested': ['Not tested', 'Не проверялось'],
  unsupported: ['Unsupported', 'Не поддерживается'],
  error: ['Error', 'Ошибка'],
};
export const ATTEMPT_TEXT: Record<CapabilityState['attempt'], [string, string]> = {
  verified: ['Ready', 'Готово'],
  unverified: ['Can be tried', 'Можно попробовать'],
  'confirmed-only': ['Only after confirmation', 'Только после подтверждения'],
  blocked: ['Blocked', 'Заблокировано'],
};

export function opState(device: Device | undefined, op: string): CapabilityState | undefined {
  return device?.capability_matrix?.[op];
}

/** Why an operation cannot be used, or null when it may be tried. No matrix = no objection. */
export function blockedReason(
  device: Device | undefined,
  ...ops: string[]
): { op: string; status: CapabilityState['status']; evidence: string } | null {
  if (!device) return null;
  if (!device.capability_matrix) return null;
  // Several operations: at least one usable is enough (e.g. direct upload or staged upload).
  const states = ops.map((op) => [op, opState(device, op)] as const);
  if (states.some(([, s]) => s && s.attempt !== 'blocked')) return null;
  const [op, s] = states[0] ?? ['', undefined];
  return {
    op,
    status: s?.status ?? 'not-tested',
    evidence: s?.evidence ?? 'No probe result for this operation',
  };
}

/**
 * For workflows that cannot run on an unprobed read (they need the verified native adapter):
 * why the operation is not *verified*, or null when a probe succeeded.
 */
export function unverifiedReason(
  device: Device | undefined,
  op: string,
): { op: string; status: CapabilityState['status']; evidence: string } | null {
  if (!device?.capability_matrix) return null;
  const state = opState(device, op);
  if (state?.status === 'available') return null;
  return {
    op,
    status: state?.status ?? 'not-tested',
    evidence: state?.evidence ?? 'No probe result for this operation',
  };
}

/** Identity of a connection for cache invalidation: changes with phone, link, profile, firmware. */
export function connectionKey(device: Device): string {
  return `${device.connected ? 1 : 0}:${device.capability_fingerprint ?? ''}`;
}
