import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from symport.config import Config  # noqa: E402
from tests.helpers import REPO  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Tests must not depend on whatever SDKs are installed on the host."""
    for k in ("SYMPORT_MAKESIS", "SYMPORT_SIGNSIS", "SYMPORT_SYMBIAN", "SYMPORT_EKA2L1", "SYMPORT_REPO",
              "SYMPORT_PROFILES", "SYMPORT_SIGN_PASSPHRASE", "EPOCROOT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PATH", os.pathsep.join(
        p for p in os.environ.get("PATH", "").split(os.pathsep)
        if not any((Path(p) / n).exists() for n in ("makesis", "signsis", "symbian", "eka2l1", "eka2l1_qt"))))


@pytest.fixture
def repo():
    return REPO


@pytest.fixture
def cfg():
    return Config.load(REPO)
