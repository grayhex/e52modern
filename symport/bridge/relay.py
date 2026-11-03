"""Outbound HTTPS relay, enrolled by the local operator. No inbound Internet port."""

from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .server import DANGEROUS, MAX_BODY


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def validate_origin(origin):
    try:
        value = urlsplit(origin)
        valid = value.scheme == "https" or (
            value.scheme == "http" and value.hostname in ("127.0.0.1", "localhost")
        )
        if (
            not valid
            or value.username
            or value.password
            or value.path
            or value.query
            or value.fragment
            or not value.hostname
        ):
            raise ValueError("Use an HTTPS SymPort origin, or a local HTTP Workbench")
        return origin
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid SymPort origin") from exc


class OutboundRelay:
    def __init__(self, agent, origin, token):
        self.agent, self.origin, self.token = agent, validate_origin(origin), token
        self.stop = threading.Event()
        self.opener = build_opener(NoRedirect())
        self.thread = threading.Thread(target=self.run, daemon=True, name="bridge-outbound")

    def call(self, action, body):
        request = Request(
            self.origin + "/api/bridge-relay/" + action,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "X-Symport-Relay-Key": self.token},
        )
        with self.opener.open(request, timeout=30) as response:
            raw = response.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise ValueError("Oversized relay request")
        return json.loads(raw)

    def run(self):
        while not self.stop.is_set() and not self.agent.stop.is_set():
            try:
                message = self.call("poll", {})
                work = message.get("request")
                if not work:
                    continue
                if self.stop.is_set():
                    break
                data = work["data"]
                try:
                    if data.get("action") in DANGEROUS and (
                        data.get("confirm") is not True
                        or not self.agent.server.approve
                        or not self.agent.server.approve(data)
                    ):
                        raise ValueError("Local approval required")
                    result = self.agent.manager.execute(data)
                except (ValueError, OSError):
                    result = {
                        "error": "The local transport could not complete the operation. Check Bridge diagnostics; read the phone before retrying a write."
                    }
                # A lost result is never retried: no accidental repeated SMS/writes.
                self.call("result", {"id": work["id"], "result": result})
            except HTTPError as exc:
                if exc.code in (401, 403):
                    break
                if self.stop.wait(3):
                    break
            except Exception:
                if self.stop.wait(3):
                    break
