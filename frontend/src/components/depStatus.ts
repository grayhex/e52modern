export type Tone = 'ok' | 'warn' | 'bad';
const labels: Record<string, [string, string, Tone]> = {
  'satisfied-static': ['Statically satisfied', 'Статически выполнено', 'ok'],
  unresolved: [
    'Unresolved: some requirements are unverified',
    'Не решено: часть требований не подтверждена',
    'warn',
  ],
  blocked: ['Blocked by a known conflict', 'Заблокировано известным конфликтом', 'bad'],
  'supported-static': ['Platform accepted (static)', 'Платформа принята (статически)', 'ok'],
  unsupported: ['Platform not accepted', 'Платформа не принимается', 'bad'],
  unknown: ['Unknown', 'Неизвестно', 'warn'],
  'accepted-by-target': ['Accepted by target', 'Принята целью', 'ok'],
  'not-accepted-by-target': ['Not accepted by target', 'Не принята целью', 'bad'],
  'target-unknown': ['Target model not selected', 'Модель не выбрана', 'warn'],
  'unknown-platform-id': ['Unrecognised platform ID', 'Неизвестный ID платформы', 'warn'],
  'required-unverified': ['Required, not verified', 'Требуется, не подтверждено', 'warn'],
  'runtime-required-unverified': [
    'Runtime required, not verified',
    'Нужен runtime, не подтверждено',
    'warn',
  ],
  'provided-by-bundle': ['Supplied in kit', 'Есть в комплекте', 'ok'],
  'provided-by-bundle-by-name': [
    'Supplied in kit (matched by name only)',
    'Есть в комплекте (по имени, не по UID)',
    'warn',
  ],
  'provided-version-unknown': ['Supplied, version unknown', 'Есть, версия неизвестна', 'warn'],
  'provided-version-too-old': [
    'Supplied version too old',
    'Версия в комплекте слишком старая',
    'bad',
  ],
  'package-provided': ['Inside the package', 'Внутри пакета', 'ok'],
  'firmware-profile-present': [
    'Present in the supplied firmware',
    'Есть в загруженной прошивке',
    'ok',
  ],
  'firmware-profile-missing': [
    'Missing from the supplied firmware',
    'Нет в загруженной прошивке',
    'bad',
  ],
  'unknown-no-firmware-data': [
    'Unknown: no firmware data',
    'Неизвестно: нет данных прошивки',
    'warn',
  ],
};
export const issueText: Record<string, [string, string]> = {
  'platform-undeclared': [
    'The package declares no platform IDs.',
    'Пакет не объявляет ID платформы.',
  ],
  'platform-target-unknown': [
    'Choose the Nokia model to evaluate platform IDs.',
    'Выберите модель Nokia, чтобы оценить ID платформы.',
  ],
  'platform-unsupported': [
    'None of the declared platforms matches the selected phone.',
    'Ни одна объявленная платформа не подходит выбранному телефону.',
  ],
  'legacy-platform-not-assessed': [
    'S60 2nd Edition (Symbian 7.0s) is not assessed: SymPort has no verified rules for it.',
    'S60 2nd Edition (Symbian 7.0s) не оценивается: у SymPort нет проверенных правил для этой платформы.',
  ],
  'dependency-unverified': [
    'A declared dependency is not supplied; it is NOT assumed installed.',
    'Объявленная зависимость не предоставлена; она НЕ считается установленной.',
  ],
  'dependency-version': [
    'A supplied dependency is older than required.',
    'Предоставленная зависимость старше требуемой.',
  ],
  'runtime-required-unverified': [
    'A runtime is required and its presence on the phone is unknown.',
    'Нужен runtime, его наличие на телефоне неизвестно.',
  ],
  'imports-undecoded': [
    'Compressed executables: imported DLLs could not be read.',
    'Сжатые исполняемые файлы: импортируемые DLL прочитать не удалось.',
  ],
  'system-dll-unverified': [
    'System DLL imports cannot be checked without firmware data.',
    'Импорты системных DLL нельзя проверить без данных прошивки.',
  ],
  'system-dll-missing': [
    'An imported DLL is missing from the supplied firmware.',
    'Импортируемой DLL нет в загруженной прошивке.',
  ],
  'restricted-capabilities': [
    'Restricted capabilities need a certificate the phone trusts.',
    'Ограниченные capabilities требуют сертификата, которому доверяет телефон.',
  ],
  'payload-unreadable': [
    'The package payload could not be fully read.',
    'Содержимое пакета прочитано не полностью.',
  ],
};
export function statusLabel(
  status: string | null | undefined,
  t: (en: string, ru: string) => string,
) {
  const entry = status ? labels[status] : undefined;
  return { text: entry ? t(entry[0], entry[1]) : (status ?? '—'), tone: entry?.[2] ?? 'warn' };
}
