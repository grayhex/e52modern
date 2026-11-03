"""Google CSV / Apple and Google vCard interchange, without cloud credentials.

Only name, structured name, phone numbers and email addresses are imported.
Unsupported fields are reported, not silently represented as synchronised data.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import re

import vobject

MAX_CONTACTS = 2000
MAX_SOURCE = 4 * 1024 * 1024


def clean(value: object, limit: int = 300) -> str:
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError('Недопустимое поле контакта: проверьте длину и управляющие символы')
    return value.strip()


def normalize(data: list[dict]) -> list[dict]:
    if not isinstance(data, list) or not 0 < len(data) <= MAX_CONTACTS:
        raise ValueError('Выберите от 1 до 2000 контактов')
    result = []
    for row in data:
        if not isinstance(row, dict):
            raise ValueError('Некорректный контакт')
        item = {k: clean(row.get(k, '')) for k in ('name', 'given', 'family')}
        for key in ('phones', 'emails'):
            values = row.get(key, [])
            if not isinstance(values, list) or len(values) > 30:
                raise ValueError('Слишком много номеров или адресов у контакта')
            item[key] = list(dict.fromkeys(clean(v) for v in values if v))
        item['name'] = item['name'] or ' '.join(filter(None, (item['given'], item['family'])))
        if not item['name']:
            item['name'] = next(iter(item['phones'] or item['emails']), '')
        if not item['name']:
            raise ValueError('Контакт без имени, номера и адреса')
        result.append(item)
    return result


def signature(contact: dict) -> str:
    numbers = sorted(re.sub(r'[^\d+]', '', p) for p in contact['phones'])
    return hashlib.sha256(repr((contact['name'].casefold(), numbers,
                               sorted(e.casefold() for e in contact['emails']))).encode()).hexdigest()


def parse_export(filename: str, content: str) -> dict:
    if not isinstance(filename, str) or not isinstance(content, str):
        raise ValueError('Нужен файл CSV или vCard')
    raw = base64.b64decode(content, validate=True)
    if len(raw) > MAX_SOURCE:
        raise ValueError('Экспорт контактов должен быть не больше 4 МиБ')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('Сохраните экспорт в UTF-8 (Google CSV или vCard)') from exc
    contacts, warnings = [], []
    if filename.lower().endswith('.csv'):
        reader = csv.DictReader(io.StringIO(text))
        columns = reader.fieldnames or []
        if not any(k in columns for k in ('Name', 'First Name', 'Given Name', 'Full Name')):
            raise ValueError('Неизвестные столбцы CSV. Выберите формат Google CSV или экспорт vCard')
        for row in reader:
            if not any(row.values()):
                continue
            if len(contacts) >= MAX_CONTACTS:
                raise ValueError('Максимум 2000 контактов за один импорт')
            def values(pattern, row=row):
                return [v.strip() for k, value in row.items() if k and re.fullmatch(pattern, k)
                        for v in (value or '').split(' ::: ') if v.strip()]
            contacts.append({'name': row.get('Name') or row.get('Full Name') or '',
                             'given': row.get('First Name') or row.get('Given Name') or '',
                             'family': row.get('Last Name') or row.get('Family Name') or '',
                             'phones': values(r'Phone \d+ - Value'),
                             'emails': values(r'E-?mail \d+ - Value')})
    elif filename.lower().endswith(('.vcf', '.vcard')):
        try:
            for card in vobject.readComponents(text):
                if card.name != 'VCARD':
                    raise ValueError('Файл содержит данные другого типа')
                if len(contacts) >= MAX_CONTACTS:
                    raise ValueError('Максимум 2000 контактов за один импорт')
                name = card.contents.get('n', [None])[0]
                n = name.value if name else None
                contacts.append({'name': str(card.fn.value) if hasattr(card, 'fn') else '',
                                 'given': str(n.given) if n else '', 'family': str(n.family) if n else '',
                                 'phones': [str(p.value).removeprefix('tel:') for p in card.contents.get('tel', [])],
                                 'emails': [str(e.value) for e in card.contents.get('email', [])]})
        except (vobject.base.ParseError, vobject.base.ValidateError, AttributeError) as exc:
            raise ValueError('Не удалось разобрать vCard. Повторите экспорт из Contacts') from exc
    else:
        raise ValueError('Поддерживаются Google CSV и vCard (.vcf) Apple/Google Contacts')
    normalized = normalize(contacts)
    unique, seen, duplicates = [], set(), 0
    for contact in normalized:
        key = signature(contact)
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
            unique.append(contact)
    warnings.append('Переносятся имена, телефоны и email. Фото, группы, адреса, заметки и метки не переносятся.')
    if duplicates:
        warnings.append(f'Убраны точные дубли внутри файла: {duplicates}. Дубли на телефоне проверяются отдельно.')
    return {'contacts': unique, 'warnings': warnings, 'duplicates': duplicates,
            'source_sha256': hashlib.sha256(raw).hexdigest()}


def vcards(contacts: list[dict]) -> list[str]:
    cards = []
    for contact in normalize(contacts):
        card = vobject.vCard()
        card.add('fn').value = contact['name']
        card.add('n').value = vobject.vcard.Name(given=contact['given'], family=contact['family'])
        for phone in contact['phones']:
            card.add('tel').value = phone
        for email in contact['emails']:
            card.add('email').value = email
        cards.append(card.serialize())
    return cards
