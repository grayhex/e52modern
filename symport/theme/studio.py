"""Private editable theme projects; bounded parsing, opaque resources and explicit unsigned builds."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import secrets
import struct
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

from symport.catalog.packages import validate_package
from symport.catalog.service import save
from symport.phone.registry import selectable_profiles
from symport.sis.reader import extract, inspect
from symport.sis.writer import SisDependency, SisFile, SisPackage, build
from symport.theme.inspect import contrast

KEY = re.compile(r"^[a-f0-9]{24}$")
RESOURCE = re.compile(
    r"^(?:[!cCeE]:\\resource\\skins\\[a-fA-F0-9]{8}\\[^\\]+\.(?:mbm|mif)|[!cCeE]:\\private\\10207114\\import\\[a-fA-F0-9]{8}\\[^\\]+\.skn)$",
    re.I,
)

PROFILES = {key:(p["screen"]["width"],p["screen"]["height"]) for key,p in selectable_profiles().items()}


class ThemeStudio:
    def __init__(self, repo):
        self.repo, self.root, self.lock = (
            repo,
            repo / "build/symport/theme-studio",
            threading.RLock(),
        )
        self.tools = Path(__file__).resolve().parents[2] / "tools/s60"
        self.source_repo = Path(__file__).resolve().parents[2]
        self.palette = json.loads(
            (self.source_repo / "theme/colours.json").read_text(encoding="utf-8")
        )

    def folder(self, key):
        if not isinstance(key, str) or not KEY.fullmatch(key):
            raise ValueError("Invalid theme project ID")
        return self.root / key

    def get(self, key):
        folder = self.folder(key)
        if not (folder / "project.json").is_file():
            raise ValueError("Theme project not found")
        return json.loads((folder / "project.json").read_text(encoding="utf-8"))

    def store(self, project):
        project["updated"] = datetime.now(UTC).isoformat()
        save(self.folder(project["id"]) / "project.json", project)
        return project

    def inventory(self, folder, files):
        result = []
        for index, (target, raw) in enumerate(files.items()):
            key = f"{index:03d}"
            (folder / ("resource-" + key)).write_bytes(raw)
            extension = Path(target.replace("\\", "/")).suffix.lower()[1:]
            row = {
                "id": key,
                "target": target,
                "name": target.rsplit("\\", 1)[-1],
                "kind": extension,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "editable": bool(RESOURCE.fullmatch(target)),
            }
            if extension == "mbm":
                row["bitmaps"] = self.mbm(raw)
            elif extension == "mif":
                row["structure"] = self.mif(raw)
            elif extension == "skn":
                row["structure"] = self.skn(raw)
            result.append(row)
        return result

    @staticmethod
    def mbm(raw):
        if len(raw) < 24 or struct.unpack_from("<II", raw) != (0x10000037, 0x10000042):
            raise ValueError("Unsupported MBM container")
        trailer = struct.unpack_from("<I", raw, 16)[0]
        if trailer + 4 > len(raw):
            raise ValueError("MBM trailer outside file")
        count = struct.unpack_from("<I", raw, trailer)[0]
        if not 0 < count <= 512 or trailer + 4 + count * 4 > len(raw):
            raise ValueError("MBM bitmap count/table exceeds limits")
        rows = []
        for index in range(count):
            offset = struct.unpack_from("<I", raw, trailer + 4 + index * 4)[0]
            if offset + 40 > len(raw):
                raise ValueError("Truncated MBM bitmap")
            size, header, width, height, _tw, _th, depth, colour, palette, compression = (
                struct.unpack_from("<10I", raw, offset)
            )
            if (
                header != 40
                or size < header
                or offset + size > len(raw)
                or not 0 < width <= 2048
                or not 0 < height <= 2048
                or width * height > 2_000_000
            ):
                raise ValueError("MBM bitmap dimensions or size exceed limits")
            rows.append(
                {
                    "index": index,
                    "width": width,
                    "height": height,
                    "depth": depth,
                    "compression": compression,
                    "editable": ((depth == 8 and colour == 0) or (depth == 16 and colour == 1))
                    and not palette
                    and compression in (0, 1, 2, 3, 4, 5, 6),
                }
            )
        if sum(row["width"] * row["height"] for row in rows) > 16_000_000:
            raise ValueError("MBM total decoded pixel limit exceeded")
        return rows

    @staticmethod
    def mif(raw):
        if len(raw) < 16:
            raise ValueError("Truncated MIF")
        uid, version, offset, count = struct.unpack_from("<4I", raw)
        if (
            uid != 0x34232342
            or version != 2
            or count > 1024
            or count % 2
            or offset < 16
            or offset + count * 8 > len(raw)
        ):
            raise ValueError("Unsupported MIF table/version")
        embedded = 0
        for index in range(count):
            start, length = struct.unpack_from("<ii", raw, offset + index * 8)
            if start > 0:
                if length <= 0 or start < offset + count * 8 or start + length > len(raw):
                    raise ValueError("Embedded MIF data exceeds container bounds")
                embedded += 1
        return {
            "version": version,
            "icons": count // 2,
            "embedded_svg": embedded,
            "status": "opaque-svg" if embedded else "bitmap-references",
        }

    @staticmethod
    def skn(raw):
        if len(raw) < 16 or struct.unpack_from("<I", raw)[0] != len(raw):
            raise ValueError("Invalid SKN envelope")
        return {
            "length": len(raw),
            "type": struct.unpack_from("<H", raw, 4)[0],
            "version": struct.unpack_from("<H", raw, 6)[0],
            "uid": f"{struct.unpack_from('<I', raw, 8)[0]:08x}",
            "status": "opaque-preserved",
            "reason": "Compiled SKN item/color tables are not reversibly decoded. Replace a validated resource or create an editable CLEAR project.",
        }

    @staticmethod
    def image(content, size=None):
        from PIL import Image, ImageOps

        try:
            raw = base64.b64decode(content, validate=True)
            if not 0 < len(raw) <= 4 * 1024**2:
                raise ValueError("Image limit: 4 MiB")
            with Image.open(io.BytesIO(raw)) as source:
                if source.width * source.height > 16_000_000:
                    raise ValueError("Image exceeds 16 megapixels")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGBA")
                if size:
                    image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
                output = io.BytesIO()
                image.save(output, "PNG")
                return output.getvalue()
        except (OSError, TypeError, Image.DecompressionBombError) as exc:
            raise ValueError("Choose a supported raster image") from exc

    def file(self, key):
        project = self.get(key)
        if project.get("built_revision") != project["revision"]:
            raise ValueError("Build the current theme revision first")
        raw = (self.folder(key) / "theme.sis").read_bytes()
        if hashlib.sha256(raw).hexdigest() != project["build"]["sha256"]:
            raise ValueError("Theme output integrity changed; build again")
        return "SymPort-" + key[:8] + ".sis", raw, "theme"

    def execute(self, data):
        with self.lock:
            try:
                return self._execute(data)
            except subprocess.TimeoutExpired as exc:
                raise ValueError("Theme processing timed out; original SIS is retained") from exc

    def _execute(self, data):
        action = data.get("action")
        if action == "list":
            return {
                "projects": [
                    json.loads(p.read_text(encoding="utf-8"))
                    for p in sorted(
                        self.root.glob("*/project.json"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )[:40]
                ],
                "profiles": {k: list(v) for k, v in PROFILES.items()},
                "palettes": {k: v["palette"] for k, v in self.palette.items()},
                "limitations": [
                    "Preview is a schematic design preview, not a firmware screenshot.",
                    "Theme resources do not change S60 menu geometry, key assignments or system layout.",
                    "Imported binary SKN palettes and embedded SVG-T/MIF are preserved as opaque resources; no false reversible editor is offered.",
                ],
            }
        if action in ("create", "import"):
            if len(list(self.root.glob("*/project.json"))) >= 40:
                raise ValueError("Maximum 40 theme projects; remove an unused project")
            profile, name = data.get("profile", "nokia-e52"), data.get("name", "SymPort Theme")
            if (
                profile not in PROFILES
                or not isinstance(name, str)
                or not 1 <= len(name) <= 60
                or any(ord(c) < 32 or ord(c) > 126 or c in '"\\' for c in name)
            ):
                raise ValueError(
                    "Choose a supported Nokia profile and a printable ASCII theme name (1–60 characters)"
                )
            key = secrets.token_hex(12)
            folder = self.folder(key)
            folder.mkdir(parents=True, mode=0o700)
            try:
                project = {
                    "id": key,
                    "name": name,
                    "profile": profile,
                    "mode": "clear",
                    "uid": 0xE1000000 | secrets.randbits(24),
                    "revision": 1,
                    "palette": dict(
                        self.palette.get(data.get("variant"), self.palette["light"])["palette"]
                    ),
                    "icons": {},
                    "wallpaper": False,
                    "resources": [],
                    "blockers": [],
                    "physical_device": "not-tested",
                }
                if action == "import":
                    raw = base64.b64decode(data.get("content", ""), validate=True)
                    if not 0 < len(raw) <= 8 * 1024**2:
                        raise ValueError("SIS theme limit: 8 MiB")
                    validate_package("theme.sis", raw)
                    info = inspect(raw)
                    if not all(
                        info.get(k) for k in ("uid_checksum_ok", "controller_crc_ok", "data_crc_ok")
                    ):
                        raise ValueError("SIS checksums failed")
                    files = extract(raw)
                    if len(files) > 100 or sum(map(len, files.values())) > 16 * 1024**2:
                        raise ValueError("Theme resource count/size exceeds limits")
                    resources = self.inventory(folder, files)
                    project.update(
                        mode="imported",
                        uid=info["package"]["uid"],
                        resources=resources,
                        original={
                            "name": data.get("filename", "theme.sis"),
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "signed": info["signed"],
                            "package": info["package"],
                        },
                    )
                    (folder / "original.sis").write_bytes(raw)
                    if (
                        not resources
                        or not all(r["editable"] for r in resources)
                        or not any(r["kind"] == "skn" for r in resources)
                    ):
                        project["blockers"].append(
                            "Import contains non-theme paths or no SKN; unsigned repack is blocked"
                        )
                    if info.get("undecoded_blocks") or info.get("data_units") != 1:
                        project["blockers"].append(
                            "Conditional/embedded SIS semantics cannot be preserved by the writer"
                        )
                    if len(files) != len(info["files"]) or any(
                        f.get("operation") != 1
                        or f.get("operation_options")
                        or f.get("mime_type")
                        or f.get("capabilities_raw")
                        for f in info["files"]
                    ):
                        project["blockers"].append(
                            "Nonstandard file operations/options or duplicate targets cannot be preserved by repack"
                        )
                    project["dependencies"] = info.get("dependencies", {}).get("items", [])
                    if any(d["kind"] == "target-device" and (
                        d.get("uid") not in selectable_profiles()[profile]["platform_uids"]
                        or d.get("from_version") not in (None, [0, 0, 0]) or d.get("to_version")
                    ) for d in project["dependencies"]):
                        project["blockers"].append("Imported platform/version constraints cannot be safely preserved for the selected model")
                    if (
                        info["package"].get("version") is None
                        or len(info["package"].get("names", [])) != 1
                        or len(info["package"].get("vendor_names", [])) != 1
                    ):
                        project["blockers"].append(
                            "Multilingual or undecoded package metadata cannot be preserved by this writer"
                        )
                return self.store(project)
            except Exception:
                import shutil

                shutil.rmtree(folder, ignore_errors=True)
                raise

        project = self.get(data.get("id"))
        folder = self.folder(project["id"])
        if action == "project":
            return project
        if action == "delete":
            if data.get("confirm") is not True:
                raise ValueError("Confirm project deletion")
            import shutil

            shutil.rmtree(folder)
            return {"deleted": True}
        if action == "export":
            name, raw, _ = self.file(project["id"])
            return {
                "name": name,
                "content": base64.b64encode(raw).decode(),
                "mime": "application/vnd.symbian.install",
            }
        if action == "asset":
            if data.get("asset") == "icon" and data.get("uid") in project["icons"]:
                uid = data["uid"]
                raw = (folder / ("icon-" + uid + ".png")).read_bytes()
                return {
                    "name": "icon-" + uid + ".png",
                    "content": base64.b64encode(raw).decode(),
                    "mime": "image/png",
                }
            if data.get("asset") == "wallpaper" and project.get("wallpaper"):
                raw = (folder / "wallpaper.png").read_bytes()
                return {
                    "name": "wallpaper.png",
                    "content": base64.b64encode(raw).decode(),
                    "mime": "image/png",
                }
            resource = next(
                (r for r in project["resources"] if r["id"] == data.get("resource")), None
            )
            if not resource:
                raise ValueError("Select a project resource")
            raw = (folder / ("resource-" + resource["id"])).read_bytes()
            return {
                "name": resource["name"],
                "content": base64.b64encode(raw).decode(),
                "mime": "application/octet-stream",
            }
        if action in ("bitmap-preview", "bitmap-replace"):
            resource = next(
                (
                    r
                    for r in project["resources"]
                    if r["id"] == data.get("resource") and r["kind"] == "mbm"
                ),
                None,
            )
            index = data.get("index")
            if not resource or type(index) is not int or not 0 <= index < len(resource["bitmaps"]):
                raise ValueError("Select a valid bitmap index")
            if not all(row["editable"] for row in resource["bitmaps"]):
                raise ValueError(
                    "This MBM depth/palette is not supported by lossless bitmap editing; use whole-resource replacement"
                )
            if not (self.tools / "bin/bmconv").is_file():
                raise ValueError("Build bmconv with tools/s60/build.sh (included in Docker)")
            if action == "bitmap-replace":
                if project["mode"] != "imported":
                    raise ValueError(
                        "Generated resources are rebuilt from palette/assets; import the SIS for individual bitmap edits"
                    )
                if data.get("revision") != project["revision"]:
                    raise ValueError("Theme revision changed; reload first")
                row = resource["bitmaps"][index]
                (folder / "bitmap-replacement.png").write_bytes(
                    self.image(data.get("content"), (row["width"], row["height"]))
                )
            save(
                folder / "bitmap-task.json",
                {
                    "resource": resource["id"],
                    "index": index,
                    "bitmaps": resource["bitmaps"],
                    "replace": action == "bitmap-replace",
                },
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "symport.theme.studio_worker",
                    str(self.source_repo),
                    str(folder.resolve()),
                    "bitmap",
                ],
                cwd=self.source_repo,
                capture_output=True,
                timeout=50,
                check=False,
            )
            if result.returncode:
                raise ValueError(
                    "bmconv could not decode/rebuild this bitmap resource; original resource retained"
                )
            if action == "bitmap-preview":
                return {
                    "name": "bitmap.png",
                    "content": base64.b64encode(
                        (folder / "bitmap-preview.png").read_bytes()
                    ).decode(),
                    "mime": "image/png",
                }
            raw = (folder / "bitmap-output.mbm").read_bytes()
            checked = self.mbm(raw)
            if [(r["width"], r["height"], r["depth"]) for r in checked] != [
                (r["width"], r["height"], r["depth"]) for r in resource["bitmaps"]
            ]:
                raise ValueError("MBM read-back changed the resource layout; original retained")
            (folder / ("resource-" + resource["id"])).write_bytes(raw)
            resource.update(bitmaps=checked, size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            project["revision"] += 1
            project["built_revision"] = None
            return self.store(project)
        if data.get("revision") != project["revision"]:
            raise ValueError("Theme changed in another view; reload before editing/building")
        if action == "save":
            if project["mode"] != "clear":
                raise ValueError("Imported compiled palettes are opaque; use a CLEAR project")
            palette = data.get("palette")
            if (
                not isinstance(palette, dict)
                or set(palette) != set(project["palette"])
                or any(
                    not isinstance(v, str) or not re.fullmatch(r"#[a-fA-F0-9]{6}", v)
                    for v in palette.values()
                )
            ):
                raise ValueError("Provide all declared palette roles as #RRGGBB")
            project["palette"] = palette
            project["contrast"] = [
                {"foreground": a, "background": b, "ratio": contrast(palette[a], palette[b])}
                for a, b in [
                    ("text", "bg"),
                    ("text", "panel"),
                    ("hl_text", "hl_fill_bot"),
                    ("softkey_text", "softkey"),
                ]
            ]
        elif action in ("wallpaper-remove", "icon-remove"):
            if project["mode"] != "clear":
                raise ValueError("Use resource replacement for imported themes")
            if action == "wallpaper-remove":
                (folder / "wallpaper.png").unlink(missing_ok=True)
                project["wallpaper"] = False
            else:
                uid = data.get("uid")
                if uid not in project["icons"]:
                    raise ValueError("Choose a project application icon")
                (folder / ("icon-" + uid + ".png")).unlink(missing_ok=True)
                del project["icons"][uid]
        elif action in ("wallpaper", "icon"):
            if project["mode"] != "clear":
                raise ValueError("Use resource replacement for imported themes")
            if action == "wallpaper":
                raw = self.image(data.get("content"), PROFILES[project["profile"]])
                (folder / "wallpaper.png").write_bytes(raw)
                project["wallpaper"] = True
            else:
                uid = data.get("uid", "")
                if (
                    not isinstance(uid, str)
                    or not re.fullmatch(r"[a-fA-F0-9]{8}", uid)
                    or int(uid, 16) == 0
                ):
                    raise ValueError("Enter an 8-digit application UID")
                if len(project["icons"]) >= 24 and uid.lower() not in project["icons"]:
                    raise ValueError("Maximum 24 application icons")
                uid = uid.lower()
                (folder / ("icon-" + uid + ".png")).write_bytes(
                    self.image(data.get("content"), (48, 48))
                )
                project["icons"][uid] = {"width": 48, "height": 48}
        elif action == "resource-replace":
            resource = next(
                (r for r in project["resources"] if r["id"] == data.get("resource")), None
            )
            if not resource or project["mode"] != "imported" or not resource["editable"]:
                raise ValueError("Resource replacement is unavailable")
            raw = base64.b64decode(data.get("content", ""), validate=True)
            if not 0 < len(raw) <= 8 * 1024**2:
                raise ValueError("Resource limit: 8 MiB")
            if resource["kind"] == "mbm":
                resource["bitmaps"] = self.mbm(raw)
            elif resource["kind"] == "mif":
                resource["structure"] = self.mif(raw)
            else:
                resource["structure"] = self.skn(raw)
            (folder / ("resource-" + resource["id"])).write_bytes(raw)
            resource.update(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        elif action == "build":
            if data.get("confirm_unsigned") is not True:
                raise ValueError("Explicitly acknowledge unsigned/experimental SIS output")
            if project["blockers"]:
                raise ValueError("; ".join(project["blockers"]))
            if project["mode"] == "clear":
                if (
                    not (self.tools / "bin/skc").is_file()
                    or not (self.tools / "bin/bmconv").is_file()
                ):
                    raise ValueError(
                        "Build Nokia skc/bmconv with tools/s60/build.sh (included in Docker)"
                    )
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "symport.theme.studio_worker",
                        str(self.source_repo),
                        str(folder.resolve()),
                    ],
                    cwd=self.source_repo,
                    capture_output=True,
                    timeout=90,
                    check=False,
                )
                if result.returncode:
                    raise ValueError(
                        "Nokia theme compiler failed: "
                        + (result.stderr + result.stdout).decode(errors="replace")[-1200:]
                    )
                paths = {
                    f"!:\\resource\\skins\\{project['uid']:08x}\\symportstudio.{ext}": (
                        folder / "compiled" / ("symportstudio." + ext)
                    ).read_bytes()
                    for ext in ("mbm", "mif")
                }
                paths[f"!:\\private\\10207114\\import\\{project['uid']:08x}\\symportstudio.skn"] = (
                    folder / "compiled/symportstudio.skn"
                ).read_bytes()
                dependencies = [
                    SisDependency(0xA00000EB, "Skins support"),
                    SisDependency(0x10207113, "Scalable skins"),
                ]
            else:
                paths = {
                    r["target"]: (folder / ("resource-" + r["id"])).read_bytes()
                    for r in project["resources"]
                }
                for r in project["resources"]:
                    raw = paths[r["target"]]
                    if r["kind"] == "skn" and self.skn(raw)["uid"] != f"{project['uid']:08x}":
                        raise ValueError("SKN UID differs from the package UID")
                dependencies = [
                    SisDependency(0xA00000EB, "Skins support"),
                    SisDependency(0x10207113, "Scalable skins"),
                ]
                from symport.backends.nokia_skin import load_s60inspect
                from symport.config import Config

                validator = load_s60inspect(Config.load(self.source_repo))
                for r in project["resources"]:
                    if r["kind"] == "mif" and not r["structure"].get("embedded_svg"):
                        matching = next(
                            (
                                m
                                for m in project["resources"]
                                if m["kind"] == "mbm"
                                and m["name"][:-4].lower() == r["name"][:-4].lower()
                            ),
                            None,
                        )
                        if not matching:
                            raise ValueError("No matching MBM for MIF references")
                        issues, _ = validator.inspect_mif(
                            str(folder / ("resource-" + r["id"])),
                            len(matching["bitmaps"]),
                            lambda *_: None,
                        )
                        if issues:
                            raise ValueError("; ".join(issues))
                declarations = project.get("dependencies", [])
                if any(
                    d["kind"] == "target-device"
                    and (
                        d.get("uid") not in selectable_profiles()[project["profile"]]["platform_uids"]
                        or d.get("from_version") not in (None, [0, 0, 0])
                        or d.get("to_version")
                    )
                    for d in declarations
                ):
                    raise ValueError(
                        "Imported product-specific constraints require lossless preservation before repack"
                    )
                dependencies = []
                for d in declarations:
                    if d["kind"] == "dependency":
                        if not isinstance(d.get("uid"), int) or len(d.get("names", [])) != 1:
                            raise ValueError(
                                "Undecoded dependency metadata cannot be safely rebuilt"
                            )
                        dependencies.append(
                            SisDependency(
                                d["uid"],
                                d["names"][0],
                                tuple(d.get("from_version") or [0, 0, 0]),
                                tuple(d["to_version"]) if d.get("to_version") else None,
                            )
                        )
            version = list(
                project.get("original", {}).get("package", {}).get("version") or [1, 0, 0]
            )
            if project["mode"] == "imported":
                version[2] += 1
            raw = build(
                SisPackage(
                    project["uid"],
                    project["name"],
                    "SymPort",
                    version=tuple(version),
                    files=[SisFile(target, raw) for target, raw in paths.items()],
                    platforms=[0x102032BE if selectable_profiles()[project["profile"]]["symbian"]=="9.2" else 0x101F7961],
                    dependencies=dependencies,
                )
            )
            checked = inspect(raw)
            if (
                not all(checked[k] for k in ("uid_checksum_ok", "controller_crc_ok", "data_crc_ok"))
                or extract(raw) != paths
            ):
                raise ValueError("Generated SIS failed static read-back validation")
            if project["mode"] == "clear":
                project["resources"] = self.inventory(folder, paths)
            (folder / "theme.sis").write_bytes(raw)
            project["built_revision"] = project["revision"]
            project["build"] = {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
                "status": "static-checked",
                "signature": "unsigned",
                "installation": "not-tested",
                "physical_device": "not-tested",
                "profile": project["profile"],
                "platform": selectable_profiles()[project["profile"]]["s60"],
                "firmware_resources": "not-tested",
            }
            return self.store(project)
        else:
            raise ValueError("Unknown Theme Studio operation")
        project["revision"] += 1
        project["built_revision"] = None
        return self.store(project)
