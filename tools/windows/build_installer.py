"""Build the Inno Setup installer, its SHA-256 sums and the (unsigned) update manifest.

Run after tools/windows/build_bridge.py and package_bridge.py. The manifest is signed later,
in the release job, so signing keys never exist in pull-request builds.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from symport.bridge import VERSION, update  # noqa: E402

CANDIDATES = (
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
)


def find_iscc() -> str:
    found = os.environ.get("ISCC") or shutil.which("ISCC") or next(
        (c for c in CANDIDATES if Path(c).is_file()), None
    )
    if not found:
        raise SystemExit("Inno Setup 6 (ISCC.exe) was not found; install it or set ISCC")
    return found


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--portable", type=Path, default=ROOT / "build/windows/portable")
    parser.add_argument("--out", type=Path, default=ROOT / "build/windows/installer")
    parser.add_argument("--manifest", action="store_true", help="also write bridge-update.json")
    args = parser.parse_args(argv)
    if not (args.portable / "SymPortBridge.exe").is_file():
        raise SystemExit("Build the portable bridge first (tools/windows/build_bridge.py)")
    args.out.mkdir(parents=True, exist_ok=True)
    from PIL import Image

    icon = args.out / "SymPortBridge.ico"
    with Image.open(ROOT / "symport/web_assets/brand/appmark-192.png") as image:
        image.save(icon, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    script = ROOT / "tools/windows/installer/SymPortBridge.iss"
    subprocess.run(
        [find_iscc(), "/Qp", f"/DAppVersion={args.version}", f"/DPortableDir={args.portable}",
         f"/DOutputDir={args.out}", f"/DIconFile={icon}", str(script)],
        check=True,
    )
    installer = args.out / f"SymPortBridge-Setup-{args.version}.exe"
    raw = installer.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    (args.out / "SHA256SUMS.txt").write_text(f"{digest}  {installer.name}\n", encoding="ascii")
    if args.manifest:
        tag = f"bridge-v{args.version}"
        manifest = {
            "schema": update.SCHEMA,
            "version": args.version,
            "released": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d"),
            "notes": f"SymPort Bridge {args.version}. Per-user installer; settings and pairing key are kept on update.",
            "installer": {
                "name": installer.name,
                "url": f"https://github.com/{update.REPO}/releases/download/{tag}/{installer.name}",
                "size": len(raw),
                "sha256": digest,
            },
        }
        # Same validation the Bridge applies before it will offer this update.
        update.validate_manifest(manifest, "0.0.0", "")
        (args.out / update.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"{installer.name} {len(raw)} bytes sha256={digest}")


if __name__ == "__main__":
    main()
