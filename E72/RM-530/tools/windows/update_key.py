"""Create or use the Ed25519 key that signs bridge-update.json (free, no code-signing certificate).

  python tools/windows/update_key.py generate     # prints the PUBLIC key (commit it) and the
                                                  # PRIVATE seed (store as secret BRIDGE_UPDATE_SIGNING_KEY)
  python tools/windows/update_key.py sign MANIFEST # signs in place; key from BRIDGE_UPDATE_SIGNING_KEY
"""
import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402

from symport.bridge import update  # noqa: E402


def public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def main(argv):
    if argv[:1] == ["generate"]:
        key = Ed25519PrivateKey.generate()
        seed = key.private_bytes_raw()
        print("PUBLIC (set UPDATE_PUBLIC_KEY in symport/bridge/update.py):", public_hex(key))
        print("PRIVATE seed (GitHub secret BRIDGE_UPDATE_SIGNING_KEY, never commit):", base64.b64encode(seed).decode())
        return 0
    if argv[:1] == ["sign"] and len(argv) == 2:
        secret = os.environ.get("BRIDGE_UPDATE_SIGNING_KEY", "")
        if not secret:
            if update.UPDATE_PUBLIC_KEY:
                print("BRIDGE_UPDATE_SIGNING_KEY is required: the Bridge only accepts signed updates", file=sys.stderr)
                return 1
            print("No signing key configured; manifest left unsigned (checksum only)")
            return 0
        key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(secret, validate=True))
        if update.UPDATE_PUBLIC_KEY and public_hex(key) != update.UPDATE_PUBLIC_KEY:
            print("The signing key does not match UPDATE_PUBLIC_KEY", file=sys.stderr)
            return 1
        path = Path(argv[1])
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest.pop("signature", None)
        manifest["signature"] = base64.b64encode(key.sign(update.canonical(manifest))).decode()
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        update.validate_manifest(manifest, "0.0.0", public_hex(key))
        print("Manifest signed")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
