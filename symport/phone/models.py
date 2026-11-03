"""Documented Nokia S60 model families; never measured firmware or OS versions."""

import re

S60_MODELS = {
    "E51": "3rd FP1",
    "E52": "3rd FP2",
    "E55": "3rd FP2",
    "E61": "3rd",
    "E61I": "3rd",
    "E63": "3rd FP1",
    "E65": "3rd",
    "E66": "3rd FP1",
    "E71": "3rd FP1",
    "E72": "3rd FP2",
    "E75": "3rd FP2",
    "E90": "3rd FP1",
    "N73": "3rd",
    "N78": "3rd FP2",
    "N79": "3rd FP2",
    "N81": "3rd FP1",
    "N82": "3rd FP1",
    "N85": "3rd FP2",
    "N86": "3rd FP2",
    "N95": "3rd FP1",
    "N96": "3rd FP2",
    "N97": "5th",
    "5230": "5th",
    "5530": "5th",
    "5800": "5th",
    "C5-03": "5th",
    "X6": "5th",
    "C6-00": "5th",
}


def documented_model(value: str) -> dict | None:
    for model, edition in S60_MODELS.items():
        if re.search(r"(?<![A-Z0-9])" + re.escape(model) + r"(?![A-Z0-9])", value.upper()):
            return {
                "manufacturer": "Nokia",
                "model": model,
                "s60": edition,
                "edition": "5th" if edition == "5th" else "3rd",
                "source": "documented-model-profile",
                "measured": False,
            }
    return None
