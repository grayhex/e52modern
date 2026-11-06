"""Readiness checks. Pure functions of observed facts; nothing here talks to a phone.

Every check returns ``{id, status, reason, basis, source}`` where status is one of
``ready`` / ``needs-action`` / ``unknown`` / ``unsupported`` and ``basis`` says where the
evidence comes from (``observed`` from the device, ``documented`` registry, ``manual`` typed by
the user, ``none``). Manual input never raises a check above ``needs-action`` for identity.
"""
from __future__ import annotations

from symport.phone.registry import identify, registry

from .profiles import CONFIRM_TARGETS, PLANNING_MARGIN, PROFILES

RANK = {'ready': 0, 'unknown': 1, 'needs-action': 2, 'unsupported': 3}


def check(cid, status, en, ru, basis='none', source=''):
    return {'id': cid, 'status': status, 'reason': {'en': en, 'ru': ru}, 'basis': basis, 'source': source}


def worst(statuses):
    return max(statuses, key=lambda s: RANK[s], default='unknown')


def resolve_identity(observed: dict, manual: dict) -> dict:
    """Return the registry profile (or None) with the basis of the decision and any conflict."""
    out = {'profile': None, 'basis': 'none', 'rm_mismatch': False, 'rm_unrecognised': False, 'conflict': None}
    name, rm = observed.get('model'), observed.get('rm')
    basis = 'observed'
    if not name and not rm:
        name, rm, basis = manual.get('model'), manual.get('rm'), 'manual'
        if not name and not rm:
            return out
    profile = identify(str(name or ''), rm=rm, product_code=observed.get('product_code'))
    by_name = identify(str(name or '')) if name else None
    by_rm = identify('', rm=rm) if rm else None
    if by_name and by_rm and by_name['id'] != by_rm['id']:
        out['rm_mismatch'] = True
    if rm and profile and profile['id'] != 'nokia-n95-family' and not by_rm:
        out['rm_unrecognised'] = not any(rm in p['rms'] for p in registry().values())
    if profile and profile['id'] == 'nokia-n95-family' and rm and not by_rm:
        out['rm_unrecognised'] = True
    out['profile'], out['basis'] = profile, basis
    # A manual statement that contradicts what the device reported is surfaced, never merged.
    if basis == 'observed' and (manual.get('model') or manual.get('rm')):
        other = identify(str(manual.get('model') or ''), rm=manual.get('rm'))
        if (profile or {}).get('id') != (other or {}).get('id'):
            out['conflict'] = {'observed': (profile or {}).get('id'), 'manual': (other or {}).get('id')}
    return out


def evaluate(facts: dict, profile_id: str) -> dict:
    """All checks for one wizard profile; keyed by check id."""
    wizard = PROFILES[profile_id]
    ident = facts['identity']
    prof = ident['profile']
    row = facts['row']
    caps = facts['capabilities']
    out: dict[str, dict] = {}

    # connection ---------------------------------------------------------------------------
    if not row:
        out['connection'] = check('connection', 'needs-action',
                                  'No phone connection is visible. Connect the Windows Bridge or enrol a drive.',
                                  'Подключение к телефону не обнаружено. Подключите Windows Bridge или добавьте диск.')
    elif not row.get('connected'):
        out['connection'] = check('connection', 'needs-action', 'The connection is present but not answering.',
                                  'Подключение есть, но не отвечает.', 'observed', row.get('transport') or '')
    else:
        out['connection'] = check('connection', 'ready', f"Connected via {row.get('transport')}.",
                                  f"Подключено через {row.get('transport')}.", 'observed', row.get('transport') or '')

    # identity -----------------------------------------------------------------------------
    if not prof:
        known = bool(facts.get('documented_family'))
        if known:
            out['identity'] = check('identity', 'unsupported',
                                    'This Nokia model is known but has no Revive profile yet.',
                                    'Эта модель Nokia известна, но профиля Revive для неё пока нет.', 'documented')
        else:
            out['identity'] = check('identity', 'unknown',
                                    'The model is not reported or not recognised. A mounted drive does not identify a phone.',
                                    'Модель не сообщена или не распознана. Подключённый диск не идентифицирует телефон.')
    elif ident['rm_mismatch']:
        out['identity'] = check('identity', 'needs-action',
                                'The reported model and RM code point to different phones. Check the label under the battery.',
                                'Модель и RM указывают на разные телефоны. Проверьте наклейку под аккумулятором.', ident['basis'])
    elif ident['conflict']:
        out['identity'] = check('identity', 'needs-action',
                                'What you entered contradicts what the device reported; the device report is used.',
                                'Введённые вами данные противоречат ответу устройства; используется ответ устройства.', 'observed')
    elif not prof.get('variant_known', True):
        out['identity'] = check('identity', 'needs-action',
                                'The N95 variant is unknown. Read the model suffix or RM from the phone (*#0000#).',
                                'Модификация N95 не определена. Прочитайте суффикс модели или RM на телефоне (*#0000#).', ident['basis'])
    elif prof['id'] not in wizard['targets']:
        out['identity'] = check('identity', 'unsupported',
                                f"{prof['name']} is not a target of this wizard.",
                                f"{prof.get('name_ru') or prof['name']} не входит в цели этого мастера.", ident['basis'])
    elif ident['rm_unrecognised']:
        out['identity'] = check('identity', 'needs-action',
                                'The RM code is not in the documented list; it is not treated as confirmation.',
                                'Код RM отсутствует в документированном списке и не считается подтверждением.', ident['basis'])
    elif ident['basis'] == 'manual':
        out['identity'] = check('identity', 'needs-action',
                                'Only manual input identifies the phone. Confirm on the phone (*#0000#) and use the Bridge for a device report.',
                                'Телефон определён только по ручному вводу. Подтвердите на телефоне (*#0000#) и используйте Bridge.', 'manual')
    elif prof['id'] in CONFIRM_TARGETS and not facts.get('variant_confirmed'):
        out['identity'] = check('identity', 'needs-action',
                                'This model needs your explicit confirmation of the exact variant before Revive proceeds.',
                                'Для этой модели нужно явно подтвердить точную модификацию.', 'observed')
    else:
        out['identity'] = check('identity', 'ready', f"Identified as {prof['name']}.",
                                f"Определено: {prof.get('name_ru') or prof['name']}.", ident['basis'], 'registry')

    # platform -----------------------------------------------------------------------------
    if not prof:
        out['platform'] = check('platform', 'unknown', 'Platform follows from the model, which is not identified.',
                                'Платформа определяется по модели, которая не определена.')
    elif prof.get('platform_family') == 'symbian3':
        from symport.phone.platforms import release
        current = release(row.get('os_release')) if row.get('os_source') else None
        out['platform'] = check('platform', 'ready' if current else 'unknown',
            f'Symbian^3 family; reported release: {current or "unknown"}. Model/firmware number alone does not prove Belle.',
            f'Семейство Symbian^3; версия ОС: {current or "не сообщена"}. Модель/номер прошивки не подтверждают Belle.',
            'observed' if current else 'documented', str(row.get('os_source') or 'registry'))
    elif profile_id == 'reborn-n95' and prof['s60'] != '3rd FP1':
        out['platform'] = check('platform', 'unsupported', 'Reborn for N95 needs S60 3rd Edition FP1.',
                                'Reborn для N95 требует S60 3rd Edition FP1.', 'documented', 'registry')
    else:
        out['platform'] = check('platform', 'ready', f"Documented platform: S60 {prof['s60']}, Symbian {prof.get('symbian')}. "
                                'This is the model profile, not a measured firmware version.',
                                f"Документированная платформа: S60 {prof['s60']}, Symbian {prof.get('symbian')}. "
                                'Это профиль модели, а не измеренная версия прошивки.', 'documented', 'registry')

    # firmware -----------------------------------------------------------------------------
    firmware = (facts['observed'].get('firmware') or '').strip()
    if firmware:
        out['firmware'] = check('firmware', 'ready', f'Firmware reported by the device: {firmware}.',
                                f'Прошивка, сообщённая устройством: {firmware}.', 'observed', row.get('transport') or '')
    elif facts['manual'].get('firmware'):
        out['firmware'] = check('firmware', 'needs-action', 'Firmware is only typed in; the device did not report it.',
                                'Прошивка введена вручную; устройство её не сообщило.', 'manual')
    else:
        out['firmware'] = check('firmware', 'unknown', 'The firmware version is not available over this connection.',
                                'Версия прошивки недоступна по этому подключению.')

    # storage ------------------------------------------------------------------------------
    free = facts['observed'].get('free')
    needed = facts.get('required_free', PLANNING_MARGIN)
    if _cap(caps, 'storage.read') == 'unsupported' or free is None:
        out['storage'] = check('storage', 'unknown', 'Free space is not reported by this connection.',
                               'Свободное место это подключение не сообщает.')
    elif free < needed:
        out['storage'] = check('storage', 'needs-action',
                               f'Free space {_mib(free)} MiB is below the planning margin {_mib(needed)} MiB.',
                               f'Свободно {_mib(free)} МиБ, меньше запаса {_mib(needed)} МиБ.', 'observed', row.get('storage_scope') or '')
    else:
        out['storage'] = check('storage', 'ready', f'Free space {_mib(free)} MiB on {row.get("storage_scope") or "the volume"}.',
                               f'Свободно {_mib(free)} МиБ ({row.get("storage_scope") or "том"}).', 'observed', row.get('storage_scope') or '')

    # capabilities ---------------------------------------------------------------------------
    out['files'] = _cap_check('files', caps, 'files.list', 'Listing files', 'Просмотр файлов')
    out['transfer'] = _cap_check('transfer', caps, 'packages.transfer', 'Copying a package', 'Копирование пакета')
    out['restore'] = _cap_check('restore', caps, 'files.download', 'Reading files back', 'Чтение файлов обратно')

    # rights (manual only; never a device fact) ------------------------------------------------
    rights = facts.get('rights')
    if not rights:
        out['rights'] = check('rights', 'unknown', 'Installation rights and patches are not confirmed. They cannot be read through a file transport.',
                              'Права установки и патчи не подтверждены. Через файловый транспорт их прочитать нельзя.')
    elif rights['scope'] == 'device':
        out['rights'] = check('rights', 'ready', 'You recorded device-level rights. This is your observation, not a device report.',
                              'Вы записали права уровня устройства. Это ваше наблюдение, а не отчёт устройства.', 'manual')
    else:
        out['rights'] = check('rights', 'needs-action',
                              'Rights recorded only for the memory card or none: this is not enough for system-level components.',
                              'Записаны права только для карты памяти или их нет: для системных компонентов этого мало.', 'manual')

    # baseline ---------------------------------------------------------------------------------
    out['baseline'] = (check('baseline', 'ready', 'A baseline from an earlier Revive run exists for this connection.',
                             'Для этого подключения есть исходное состояние от прошлого запуска Revive.', 'observed')
                       if facts.get('baseline') else
                       check('baseline', 'needs-action', 'No baseline yet: save one in «Diagnostics after installation» before changing the phone.',
                             'Исходного состояния нет: сохраните его в «Диагностике после установки» до изменений телефона.'))
    return out


def _cap(caps: dict, op: str) -> str:
    return (caps.get(op) or {}).get('status', 'not-tested')


def _cap_check(cid, caps, op, en, ru):
    state = caps.get(op)
    if not state:
        return check(cid, 'unknown', f'{en}: capability not reported.', f'{ru}: возможность не сообщена.')
    where = f"{state.get('source')}"
    if state['status'] == 'available':
        return check(cid, 'ready', f'{en}: verified on this connection.', f'{ru}: проверено на этом подключении.', 'observed', where)
    if state['status'] in ('unsupported',):
        return check(cid, 'unsupported', f'{en}: this transport cannot do it.', f'{ru}: этот транспорт не умеет.', 'observed', where)
    if state['status'] == 'error':
        return check(cid, 'needs-action', f'{en}: the probe failed.', f'{ru}: проверка не удалась.', 'observed', where)
    if state.get('attempt') == 'confirmed-only':
        return check(cid, 'ready', f'{en}: not probed; runs only after your confirmation and is verified by reading back.',
                     f'{ru}: не проверялось заранее; выполняется после вашего подтверждения с проверкой чтением.', 'observed', where)
    if state.get('attempt') == 'unverified':
        return check(cid, 'unknown', f'{en}: not tested yet.', f'{ru}: ещё не проверялось.', 'observed', where)
    return check(cid, 'unsupported', f'{en}: blocked on this connection.', f'{ru}: заблокировано на этом подключении.', 'observed', where)


def _mib(n):
    return round(n / (1024 * 1024))
