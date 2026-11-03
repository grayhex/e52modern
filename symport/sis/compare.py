"""Semantic comparison of two SIS packages (e.g. official MakeSIS output vs the native writer).

Compression and byte layout legitimately differ between writers, so packages are compared by what
the installer would act on: identity, names, version, installed files (target, length, SHA-1),
dependency count and signature presence.
"""
from __future__ import annotations

from . import reader


def summary(data: bytes) -> dict:
    info = reader.inspect(data)
    return {
        "uid": info["package"]["uid"], "names": info["package"]["names"],
        "vendor": info["package"]["vendor_names"], "version": info["package"]["version"],
        "files": {f["target"].lower(): {"length": f["length"], "sha1": f["sha1"], "target": f["target"]}
                  for f in info["files"]},
        "dependency_elements": info["dependencies"]["declared"],
        "dependency_uids": sorted(info["dependencies"]["uids_best_effort"]),
        "signed": info["signed"],
    }


def compare(a: bytes, b: bytes) -> list[dict]:
    """List of differences; empty means installer-relevant content is identical."""
    sa, sb = summary(a), summary(b)
    diffs: list[dict] = []
    for key in ("uid", "names", "vendor", "version", "dependency_elements", "dependency_uids", "signed"):
        if sa[key] != sb[key]:
            diffs.append({"field": key, "a": sa[key], "b": sb[key]})
    for name in sorted(set(sa["files"]) | set(sb["files"])):
        fa, fb = sa["files"].get(name), sb["files"].get(name)
        if fa is None or fb is None:
            diffs.append({"field": f"file {name}", "a": "present" if fa else "missing",
                          "b": "present" if fb else "missing"})
        elif (fa["length"], fa["sha1"]) != (fb["length"], fb["sha1"]):
            diffs.append({"field": f"file {name}", "a": fa["sha1"], "b": fb["sha1"]})
    return diffs
