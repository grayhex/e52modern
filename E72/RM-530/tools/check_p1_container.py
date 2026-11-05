#!/usr/bin/env python3
"""Disposable Docker P1 smoke; real compiler/API, no phone, ROM or external downloads.

Uses unique container/volume names and removes only resources created by this run.
Run on the Docker host after building the image (Python standard library only).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import secrets
import subprocess
import time
from http.client import HTTPConnection
from pathlib import Path


def docker(*args):
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="symport-p1-validation")
    parser.add_argument("--port", type=int, default=8878)
    parser.add_argument("--report", type=Path, default=Path("build/reports/p1-container.json"))
    args = parser.parse_args()
    key = "symport-p1-" + secrets.token_hex(6)
    volume = key + "-data"
    created = False
    token = ""

    def http(method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", args.port, timeout=100)
        data = json.dumps(body).encode() if body is not None else None
        connection.request(
            method, path, body=data, headers={"Content-Type": "application/json", **(headers or {})}
        )
        response = connection.getresponse()
        status, raw = response.status, response.read()
        connection.close()
        return status, raw

    def ready():
        nonlocal token
        for _ in range(60):
            try:
                status, raw = http("GET", "/")
                found = re.search(rb'<meta name="symport-token" content="([^"]+)"', raw)
                if status == 200 and found:
                    token = found.group(1).decode()
                    return
            except OSError:
                pass
            time.sleep(0.5)
        raise RuntimeError("Disposable SymPort container did not become ready")

    def post(endpoint, body):
        status, raw = http(
            "POST",
            endpoint,
            body,
            {"X-Symport-Token": token, "Origin": f"http://127.0.0.1:{args.port}"},
        )
        if status != 200:
            raise RuntimeError(f"{endpoint}: HTTP {status}: {raw[:500]!r}")
        return json.loads(raw)

    def start():
        docker(
            "run",
            "-d",
            "--name",
            key,
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "1g",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "-p",
            f"127.0.0.1:{args.port}:{args.port}",
            "--mount",
            f"type=volume,src={volume},dst=/srv/e52modern/build",
            args.image,
            "python",
            "-m",
            "symport.web",
            "--host",
            "0.0.0.0",
            "--port",
            str(args.port),
        )
        ready()

    try:
        docker("volume", "create", volume)
        created = True
        start()
        assert docker("exec", key, "id", "-u") == "10001"
        for endpoint, body in [
            ("/api/theme-studio", {"action": "list"}),
            ("/api/diagnostics", {"action": "history", "device": "unknown"}),
            ("/api/catalog", {"action": "collections"}),
        ]:
            assert http("POST", endpoint, body)[0] == 403
            assert (
                http(
                    "POST",
                    endpoint,
                    body,
                    {"X-Symport-Token": token, "Origin": "https://untrusted.invalid"},
                )[0]
                == 403
            )
        catalog = post("/api/catalog", {"action": "list"})
        assert all(
            any(a["id"] == key for a in catalog["apps"])
            for key in ["opera-mini", "fshell", "qremotecontrol", "internet-radio"]
        )
        collection = post(
            "/api/catalog",
            {
                "action": "collection-save",
                "name": "Container recovery check",
                "profile": "nokia-e52",
                "ids": ["s2putty"],
            },
        )
        document = post("/api/catalog", {"action": "collection-export", "id": collection["id"]})
        assert document["apps"][0]["artifacts"][0]["sha256"]
        preview = post(
            "/api/catalog",
            {"action": "recovery-plan", "id": collection["id"], "profile": "nokia-e72"},
        )
        assert preview["geometry_changed"] and preview["transfer_ids"] == ["s2putty"]
        built = []
        for profile in ["nokia-e52", "nokia-e72"]:
            project = post(
                "/api/theme-studio",
                {"action": "create", "name": "Container " + profile, "profile": profile},
            )
            project = post(
                "/api/theme-studio",
                {
                    "action": "build",
                    "id": project["id"],
                    "revision": project["revision"],
                    "confirm_unsigned": True,
                },
            )
            exported = post("/api/theme-studio", {"action": "export", "id": project["id"]})
            raw = base64.b64decode(exported["content"], validate=True)
            assert hashlib.sha256(raw).hexdigest() == project["build"]["sha256"]
            assert (
                project["build"]["status"] == "static-checked"
                and project["build"]["installation"] == "not-tested"
            )
            built.append(
                {
                    "id": project["id"],
                    "profile": profile,
                    "sha256": project["build"]["sha256"],
                    "size": len(raw),
                }
            )
        # Replace the container using the same volume; do not merely reread in-process state.
        docker("rm", "-f", key)
        start()
        assert len(post("/api/catalog", {"action": "collections"})["collections"]) == 1
        for project in built:
            exported = post("/api/theme-studio", {"action": "export", "id": project["id"]})
            assert (
                hashlib.sha256(base64.b64decode(exported["content"])).hexdigest()
                == project["sha256"]
            )
        assert (
            http(
                "POST",
                "/api/diagnostics",
                {"action": "sample", "device": "no-phone"},
                {"X-Symport-Token": token},
            )[0]
            == 400
        )
        result = {
            "image": args.image,
            "non_root": True,
            "authenticated_api": True,
            "persistent_after_container_replacement": True,
            "native_themes": built,
            "catalog_collection_pins": True,
            "physical_device": "not-tested",
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
        print(
            "PASS Docker P1: authenticated APIs, non-root compiler for E52/E72, pinned collection and exact SIS persistence after container replacement. No phone operations."
        )
    finally:
        subprocess.run(["docker", "rm", "-f", key], capture_output=True, check=False)
        if created:
            subprocess.run(["docker", "volume", "rm", volume], capture_output=True, check=False)


if __name__ == "__main__":
    main()
