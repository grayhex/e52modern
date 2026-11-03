"""Small client for the existing MGO agent. No EKA2L1 protocol/server implementation."""
from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
from urllib.parse import quote, urlsplit


class AgentError(ValueError):
    def __init__(self, message: str, status=0, code='unreachable'):
        super().__init__(message)
        self.status, self.code = status, code


class MgoClient:
    def __init__(self):
        self.url = os.getenv('SYMPORT_MGO_URL', '')
        self.token_file = os.getenv('SYMPORT_MGO_TOKEN_FILE', '')
        parsed = urlsplit(self.url)
        if self.url and (parsed.scheme not in ('http', 'https') or parsed.hostname not in ('mgo-symbian', 'localhost', '127.0.0.1') or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError('MGO URL must be an operator-configured internal agent endpoint')
        self.parsed = parsed

    def _connection(self, timeout):
        if not self.url:
            raise AgentError('Emulator Lab отключён: запустите Compose profile emulator', code='disabled')
        try:
            token = Path(self.token_file).read_text().strip() if self.token_file else os.getenv('SYMPORT_MGO_TOKEN', '')
        except OSError as exc:
            raise AgentError('MGO ещё не создал ключ доступа. Запустите опциональный сервис.', code='token-not-ready') from exc
        if len(token) < 16:
            raise AgentError('Не настроен ключ доступа к агенту MGO', code='token-not-ready')
        connection = (http.client.HTTPSConnection if self.parsed.scheme == 'https' else http.client.HTTPConnection)(self.parsed.hostname, self.parsed.port, timeout=timeout)
        return connection, {'Authorization': 'Bearer ' + token}

    @staticmethod
    def _response(response, binary=False):
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise AgentError('Agent response exceeded limit', code='response-limit')
        if response.status >= 300:
            try:
                error = json.loads(raw).get('error', {})
                code = error.get('code', 'agent-error') if isinstance(error, dict) else 'agent-error'
                message = error.get('message', 'MGO rejected request') if isinstance(error, dict) else str(error)
            except (ValueError, AttributeError):
                code, message = 'agent-error', 'MGO rejected request'
            raise AgentError(str(message)[:400], response.status, code)
        if binary:
            if response.getheader('Content-Type', '').split(';')[0] != 'image/png':
                raise AgentError('Agent did not return a PNG', code='invalid-screen')
            return raw
        try:
            result = json.loads(raw) if raw else {}
            if not isinstance(result, dict):
                raise ValueError('Expected object')
            return result
        except ValueError as exc:
            raise AgentError('MGO returned an invalid JSON object', code='invalid-response') from exc

    def request(self, method, path, body=None, timeout=15, binary=False):
        connection, headers = self._connection(timeout)
        try:
            payload = json.dumps(body).encode() if body is not None else None
            if payload is not None:
                headers['Content-Type'] = 'application/json'
            connection.request(method, path, body=payload, headers=headers)
            return self._response(connection.getresponse(), binary)
        except (OSError, http.client.HTTPException) as exc:
            raise AgentError('Агент MGO недоступен или операция прервана; проверьте состояние перед повтором') from exc
        finally:
            connection.close()

    def upload(self, route, name, stream, length, bundle=None):
        path = route + '?name=' + quote(name, safe='')
        if bundle:
            path += '&bundle=' + bundle
        connection, headers = self._connection(3600)
        headers.update({'Content-Type': 'application/octet-stream', 'Content-Length': str(length)})
        try:
            connection.putrequest('PUT', path)
            for key, value in headers.items():
                connection.putheader(key, value)
            connection.endheaders()
            remaining = length
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise AgentError('Upload interrupted before the declared length', code='upload-interrupted')
                connection.send(chunk)
                remaining -= len(chunk)
            return self._response(connection.getresponse())
        except (OSError, http.client.HTTPException) as exc:
            raise AgentError('Загрузка в MGO прервана. Повторите в новом комплекте.', code='upload-interrupted') from exc
        finally:
            connection.close()
