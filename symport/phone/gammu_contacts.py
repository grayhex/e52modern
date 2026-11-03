"""Gammu phonebook adapter. Command success alone never proves an import."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from .contacts import parse_export, signature, vcards


def _run(config: str, args: list[str]) -> None:
    try:
        result = subprocess.run(['gammu', '--config', config, *args],
                                stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=120, check=False, env={**os.environ, 'LC_ALL': 'C'})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError('Gammu недоступен или устройство не ответило. Импорт мог быть частичным; прочитайте книгу перед повтором') from exc
    if result.returncode != 0:
        # Gammu output can contain full private phonebook data.
        raise ValueError('Gammu отклонил операцию. Проверьте соединение и поддержку телефонной книги; перед повтором прочитайте контакты')


def read(config: str) -> list[dict]:
    import base64
    with tempfile.TemporaryDirectory(prefix='symport-phonebook-') as tmp:
        path = Path(tmp) / 'phone.vcf'
        _run(config, ['backup', str(path), '-yes'])
        if not path.exists():
            raise ValueError('Gammu не создал экспорт телефонной книги')
        raw = path.read_bytes()
        if not raw.strip():
            raise ValueError('Gammu вернул пустой экспорт: нельзя отличить пустую книгу от отсутствия поддержки. Запись отключена; используйте перенос vCard и импорт на телефоне')
        return parse_export('phone.vcf', base64.b64encode(raw).decode())['contacts']


def import_contacts(config: str, contacts: list[dict], confirm: bool) -> dict:
    if confirm is not True:
        raise ValueError('Подтвердите добавление контактов в память телефона')
    before = read(config)  # Fail before any writes if phonebook cannot be read.
    existing = {signature(c) for c in before}
    additions = []
    seen = set(existing)
    for contact in contacts:
        key = signature(contact)
        if key not in seen:
            additions.append(contact)
            seen.add(key)
    if not additions:
        return {'status': 'already-present', 'added': 0, 'skipped': len(contacts)}
    with tempfile.TemporaryDirectory(prefix='symport-import-') as tmp:
        path = Path(tmp) / 'contacts.vcf'
        path.write_text(''.join(vcards(additions)), encoding='utf-8', newline='')
        _run(config, ['addnew', str(path), '-yes', '-memory', 'ME'])
    after = {signature(c) for c in read(config)}
    verified = sum(signature(c) in after for c in additions)
    return {'status': 'verified-in-phonebook' if verified == len(additions) else 'partial-or-unverified',
            'verified': verified, 'requested': len(additions), 'skipped': len(contacts) - len(additions),
            'warning': 'Не повторяйте запись автоматически при частичном результате; перечитайте контакты.'}
