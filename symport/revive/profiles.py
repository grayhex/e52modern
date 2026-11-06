"""Revive wizard profiles and their operations.

An operation carries everything a user needs to judge it before anything happens: risk level,
prerequisites (checks that must be ``ready``), source, version/hash, restore point and the only
execution method SymPort allows. ``execution`` is never "install": SymPort copies files through
the existing device boundary or tells the user what to do on the phone.
"""
from __future__ import annotations

PLANNING_MARGIN = 64 * 1024 * 1024  # SymPort planning margin for kit transfers, not a measured need

# Nokia S60 3rd Edition targets served by the Revive wizards (registry ids).
S60V3_TARGETS = ("nokia-e52", "nokia-e72", "nokia-n95", "nokia-n95-8gb")
# 5th Edition: supported only after the user explicitly confirms the exact variant.
CONFIRM_TARGETS = ("nokia-n97-mini",)
COMMON_TARGETS = S60V3_TARGETS + CONFIRM_TARGETS + ("nokia-n8", "nokia-e7")

PROFILES: dict[str, dict] = {
    'network-certs': {
        'title': {'en': 'Network and certificates', 'ru': 'Сеть и сертификаты'},
        'summary': {
            'en': 'Read-only look at identity, clock and certificate readiness before HTTPS or TLS work.',
            'ru': 'Только чтение: идентификация, часы и готовность сертификатов перед работой с HTTPS и TLS.',
        },
        'targets': COMMON_TARGETS,
        'operations': ['identify-device', 'clock-check', 'certificate-review'],
    },
    'app-kit': {
        'title': {'en': 'Application kit', 'ru': 'Набор приложений'},
        'summary': {
            'en': 'Check free space and transport, copy a verified kit to the phone, install it on the phone.',
            'ru': 'Проверка места и транспорта, копирование проверенного набора на телефон, установка на телефоне.',
        },
        'targets': COMMON_TARGETS,
        'operations': ['identify-device', 'space-check', 'kit-transfer', 'kit-install-manual'],
    },
    'reborn-n95': {
        'title': {'en': 'Reborn preparation for N95', 'ru': 'Подготовка Reborn для N95'},
        'summary': {
            'en': 'Preflight for the hybrid Reborn CFW alpha. Only the N95 family; the kit is never installed by SymPort.',
            'ru': 'Предполётная проверка для гибридной Reborn CFW alpha. Только семейство N95; SymPort ничего не устанавливает.',
        },
        'targets': ('nokia-n95', 'nokia-n95-8gb'),
        'operations': ['identify-device', 'space-check', 'rights-check'],
    },
    'legacy-services': {
        'title': {'en': 'Restore services', 'ru': 'Восстановить сервисы'},
        'summary': {
            'en': 'Old system endpoints, what replaces them and what is proven. Read-only; settings are changed by you.',
            'ru': 'Старые системные адреса, чем они заменяются и что подтверждено. Только чтение; настройки меняете вы.',
        },
        'targets': S60V3_TARGETS + CONFIRM_TARGETS,
        'operations': ['identify-device', 'services-matrix', 'endpoint-diagnose', 'service-setting'],
    },
    'addons': {
        'title': {'en': 'Add-ons and patches', 'ru': 'Дополнения и патчи'},
        'summary': {
            'en': 'Compatibility-gated add-ons and a read-only Patch Manager. System patches are closed by default.',
            'ru': 'Дополнения с проверкой совместимости и Patch Manager только для чтения. Системные патчи закрыты по умолчанию.',
        },
        'targets': S60V3_TARGETS + CONFIRM_TARGETS,
        'operations': ['identify-device', 'addon-plan', 'patch-inventory'],
    },
    'post-check': {
        'title': {'en': 'Diagnostics after installation', 'ru': 'Диагностика после установки'},
        'summary': {
            'en': 'Re-read the connection and compare it with the baseline taken before; record what you saw on the phone.',
            'ru': 'Повторное чтение подключения и сравнение с исходным состоянием; запись того, что вы увидели на телефоне.',
        },
        'targets': COMMON_TARGETS,
        'operations': ['reread-device', 'compare-baseline', 'manual-observations'],
    },
}

OPERATIONS: dict[str, dict] = {
    'identify-device': {
        'title': {'en': 'Read device identity', 'ru': 'Прочитать идентификацию устройства'},
        'risk': 'low', 'execution': 'read-only', 'requires': ['connection', 'identity', 'platform', 'firmware'],
        'source': {'kind': 'device', 'ref': 'DeviceManager discover'},
        'restore_point': 'not-needed',
    },
    'clock-check': {
        'title': {'en': 'Check date, time and zone on the phone', 'ru': 'Проверить дату, время и пояс на телефоне'},
        'risk': 'low', 'execution': 'manual-on-phone', 'requires': [],
        'source': {'kind': 'manual', 'ref': 'Settings → Date and time'},
        'restore_point': 'not-needed',
        'note': {'en': 'The phone clock is not readable through the transport; record what the screen shows.',
                 'ru': 'Часы телефона недоступны через транспорт; запишите то, что видно на экране.'},
    },
    'certificate-review': {
        'title': {'en': 'Review package certificates', 'ru': 'Проверить сертификаты пакетов'},
        'risk': 'low', 'execution': 'read-only', 'requires': [],
        'source': {'kind': 'builtin', 'ref': 'Certificate Inspector'},
        'restore_point': 'not-needed',
    },
    'space-check': {
        'title': {'en': 'Check free space', 'ru': 'Проверить свободное место'},
        'risk': 'low', 'execution': 'read-only', 'requires': ['connection', 'storage'],
        'source': {'kind': 'device', 'ref': 'storage.read'},
        'restore_point': 'not-needed',
    },
    'kit-transfer': {
        'title': {'en': 'Copy a verified kit to the phone', 'ru': 'Скопировать проверенный набор на телефон'},
        'risk': 'medium', 'execution': 'bridge-transfer',
        'requires': ['connection', 'identity', 'platform', 'files', 'transfer', 'storage'],
        'source': {'kind': 'catalog', 'ref': 'Application kits'},
        'restore_point': 'recommended',
        'note': {'en': 'Copying a file is not installation.', 'ru': 'Копирование файла не является установкой.'},
    },
    'kit-install-manual': {
        'title': {'en': 'Install on the phone', 'ru': 'Установить на телефоне'},
        'risk': 'medium', 'execution': 'manual-on-phone', 'requires': ['identity'],
        'source': {'kind': 'manual', 'ref': 'File manager → open the package'},
        'restore_point': 'recommended',
        'note': {'en': 'SymPort never installs software. The result is what you saw on the phone.',
                 'ru': 'SymPort никогда не устанавливает ПО. Результат — то, что вы увидели на телефоне.'},
    },
    'rights-check': {
        'title': {'en': 'Record installation rights and patches', 'ru': 'Записать права установки и патчи'},
        'risk': 'low', 'execution': 'manual-on-phone', 'requires': ['rights'],
        'source': {'kind': 'manual', 'ref': 'ROMPatcher+ / installer status'},
        'restore_point': 'not-needed',
        'note': {'en': 'Rights cannot be read through a file transport; this is your observation, not a device fact.',
                 'ru': 'Права нельзя прочитать через файловый транспорт; это ваше наблюдение, а не факт устройства.'},
    },
    'services-matrix': {
        'title': {'en': 'Service matrix for this model', 'ru': 'Матрица сервисов для этой модели'},
        'risk': 'low', 'execution': 'read-only', 'requires': ['identity'],
        'source': {'kind': 'builtin', 'ref': 'services.json (reviewed 2026-11-05)'},
        'restore_point': 'not-needed',
    },
    'endpoint-diagnose': {
        'title': {'en': 'Check substitute hosts (from the server)', 'ru': 'Проверить хосты-заменители (с сервера)'},
        'risk': 'low', 'execution': 'read-only', 'requires': [],
        'source': {'kind': 'builtin', 'ref': 'allow-listed hosts only'},
        'restore_point': 'not-needed',
        'note': {'en': 'Runs on the SymPort server; it does not prove a Nokia phone can open the URL.',
                 'ru': 'Выполняется на сервере SymPort; не доказывает, что Nokia сможет открыть адрес.'},
    },
    'service-setting': {
        'title': {'en': 'Change a setting on the phone and record before/after', 'ru': 'Изменить настройку на телефоне и записать до/после'},
        'risk': 'medium', 'execution': 'manual-on-phone', 'requires': ['identity'],
        'source': {'kind': 'manual', 'ref': 'phone settings'},
        'restore_point': 'recommended',
        'note': {'en': 'SymPort never changes phone settings. Record the old value so it can be restored.',
                 'ru': 'SymPort не меняет настройки телефона. Запишите старое значение, чтобы вернуть его.'},
    },
    'addon-plan': {
        'title': {'en': 'Plan an add-on (dry run)', 'ru': 'Спланировать дополнение (пробный прогон)'},
        'risk': 'medium', 'execution': 'read-only', 'requires': ['identity'],
        'source': {'kind': 'builtin', 'ref': 'addons.json (reviewed 2026-11-05)'},
        'restore_point': 'recommended',
    },
    'patch-inventory': {
        'title': {'en': 'Patch inventory (typed by you)', 'ru': 'Инвентарь патчей (вводится вами)'},
        'risk': 'low', 'execution': 'manual-on-phone', 'requires': [],
        'source': {'kind': 'manual', 'ref': 'ROMPatcher+ / patch list'},
        'restore_point': 'not-needed',
    },
    'reread-device': {
        'title': {'en': 'Re-read the connection', 'ru': 'Перечитать подключение'},
        'risk': 'low', 'execution': 'read-only', 'requires': ['connection', 'identity'],
        'source': {'kind': 'device', 'ref': 'DeviceManager capabilities'},
        'restore_point': 'not-needed',
    },
    'compare-baseline': {
        'title': {'en': 'Compare with the baseline', 'ru': 'Сравнить с исходным состоянием'},
        'risk': 'low', 'execution': 'read-only', 'requires': ['baseline'],
        'source': {'kind': 'builtin', 'ref': 'Revive baseline'},
        'restore_point': 'not-needed',
    },
    'manual-observations': {
        'title': {'en': 'Record what you saw on the phone', 'ru': 'Записать, что вы увидели на телефоне'},
        'risk': 'low', 'execution': 'manual-on-phone', 'requires': [],
        'source': {'kind': 'manual', 'ref': 'Boot, Wi-Fi, HTTPS, applications'},
        'restore_point': 'not-needed',
    },
}

# Operations whose outcome the user may record after doing them on the phone.
MANUAL_OPERATIONS = tuple(k for k, v in OPERATIONS.items() if v['execution'] == 'manual-on-phone')
MANUAL_RESULTS = ('done', 'failed', 'not-tested')
RIGHTS_SCOPES = ('none', 'memory-card', 'device')
STATUSES = ('ready', 'needs-action', 'unknown', 'unsupported')
