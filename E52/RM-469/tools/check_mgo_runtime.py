"""Destructive-negative smoke test for a FRESH optional MGO service (no ROM needed).

Runs through SymPort's real authenticated client against the pinned MGO image.
Refuses an instance with installed firmware. Never tests successful E52 boot.
Run only in a disposable Compose project, as documented in docs/EMULATOR_LAB.md.
"""
from __future__ import annotations

import http.client
import io
import json
import secrets
import time

from symport.lab.client import AgentError, MgoClient


def main():
    agent = MgoClient()
    deadline = time.monotonic() + 45
    while True:
        try:
            health = agent.request('GET', '/agent/health')
            break
        except AgentError:
            if time.monotonic() > deadline:
                raise
            time.sleep(.5)
    assert not health['firmware']['devices'], 'Refusing to change a service with user firmware'
    connection = http.client.HTTPConnection(agent.parsed.hostname, agent.parsed.port, timeout=5)
    connection.request('GET', '/agent/health')
    response = connection.getresponse()
    assert response.status == 401, 'Agent health must require authentication'
    response.read()
    connection.close()
    evidence = {'agent_auth': 'required', 'host_filesystem_proxy': 'forbidden', 'engine': health['emulator'], 'physical_e52': 'not-tested', 'successful_firmware_boot': 'not-tested'}
    try:
        agent.request('POST', '/agent/instance', {'maintenance': True})
        deadline = time.monotonic() + 90
        while True:
            try:
                agent.request('GET', '/v1/status')
                break
            except AgentError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(.5)
        try:
            agent.request('GET', '/v1/files')
            raise AssertionError('Host filesystem route was exposed')
        except AgentError as exc:
            assert exc.status == 403
        keys = agent.request('GET', '/v1/keys')['keys']
        assert all(key in keys for key in ('applications', 'lsk', 'rsk', 'ok', 'up'))
        evidence['hardware_keys'] = 'available'
        evidence['capabilities'] = agent.request('GET', '/v1/capabilities')
        try:
            agent.request('GET', '/v1/screenshot?region=guest', binary=True)
            raise AssertionError('No ROM should produce no guest screenshot')
        except AgentError as exc:
            assert exc.code == 'no_screen' and exc.status == 409
            evidence['no_firmware_screen'] = exc.code
        agent.request('POST', '/v1/input/release', {})
    finally:
        agent.request('DELETE', '/agent/instance')
    # Goes through the real XML/FPSX dispatcher. Neither payload is a usable ROM.
    bundle = secrets.token_hex(16)
    for name, raw, slot in [('synthetic.vpl', b'<not-a-vpl/>', 'vpl'), ('synthetic.fpsx', b'INVALID TEST DATA', 'fpsx')]:
        agent.upload('/agent/firmware/' + slot, name, io.BytesIO(raw), len(raw), bundle)
    job = agent.request('POST', '/agent/firmware/install', {'vpl': 'synthetic.vpl', 'bundle': bundle})
    deadline = time.monotonic() + 120
    while job['state'] == 'running':
        assert time.monotonic() < deadline, 'MGO invalid firmware test timed out'
        time.sleep(.5)
        job = agent.request('GET', '/agent/jobs/' + job['id'])
    assert job['state'] == 'failed' and job.get('errorCode') == 'vpl_invalid', job
    assert not agent.request('GET', '/agent/health')['firmware']['devices']
    evidence['invalid_factory_manifest'] = job['errorCode']
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
