// Shared synthetic fixture for the screenshot and layout checks: a stub transport answers as an identified
// Nokia (E52/E72 here; any registry model works), a test volume holds files, packages come from the unit-test
// builders. Nothing here is a phone or Nokia firmware.
const { spawn, spawnSync } = require("child_process");
const fs = require("fs"), path = require("path");
const repo = path.resolve(__dirname, "../..");
const python = process.env.SYMPORT_PYTHON || "python3";
const fixture = `import sys, os, json
from pathlib import Path
from tests.test_deps import QT, sis
from tests.test_firmware import firmware, zip_bytes
from tests.helpers import make_e32
out = Path(sys.argv[1])
(out / "fw-a.zip").write_bytes(zip_bytes(firmware("1")))
(out / "demo-app.sis").write_bytes(sis(0xE0001111, "Demo App", exe=make_e32(imports={"euser.dll": [1]}), deps=[(QT, "Qt", (4, 7, 3))]))
(out / "qt.sis").write_bytes(sis(QT, "Qt", version=(4, 7, 3)))
`;
const server = `import sys, os, json, shutil
from pathlib import Path
from http.server import ThreadingHTTPServer
from symport.web import Workbench, make_handler
from symport.phone.local import LocalTransports
from tests.capfake import row
root, model, rm, port = Path(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4])
v = root / "volume"
for d in ("Images", "Music", "Documents", "Installs"):
    (v / d).mkdir(parents=True, exist_ok=True)
(v / "Images/IMG_0001.jpg").write_bytes(b"\\xff\\xd8\\xff\\xd9")
(v / "Music/ringtone.mp3").write_bytes(b"ID3" + bytes(2048))
(v / "Documents/notes.txt").write_text("test volume")
os.environ.update(SYMPORT_DEVICE_ROOTS=json.dumps({"card": str(v)}), SYMPORT_GAMMU_CONFIG="mock-only", SYMPORT_CONNECTIONS_FILE="", SYMPORT_BRIDGE_URL="", SYMPORT_MGO_URL="")
w = Workbench(root)
local = LocalTransports(root)
def devices():
    card = local.files.devices()[0]
    card.update(name="E52 card (test volume)", free=int(3.1 * 1024**3), total=int(7.4 * 1024**3))
    phone = row(dict(id="gammu", name="Nokia " + model, transport="gammu", connection_kind="gammu-usb", connected=True,
                     model="Nokia %s (%s)" % (model, rm), rm=rm, firmware="071.004" if model == "E52" else "091.004",
                     battery=82, signal=74, usb_mode="PC Suite", evidence="Synthetic screenshot transport"),
                available=["identity.read", "telemetry.read", "contacts.read", "calendar.read", "tasks.read"],
                untested_writes=["contacts.write"])
    return [card, phone]
local.devices = devices
w.devices.transport = local
ThreadingHTTPServer(("127.0.0.1", port), make_handler(w)).serve_forever()
`;

function prepare(tmp) {
  const made = spawnSync(python, ["-c", fixture, tmp], { cwd: repo, env: { ...process.env, PYTHONPATH: repo } });
  if (made.status !== 0) throw Error(made.stderr.toString());
}
const children = [];
function start(tmp, model, rm, port) {
  const root = path.join(tmp, model);
  fs.mkdirSync(root, { recursive: true });
  for (const name of ["theme", "tools", "profiles", "catalog"]) fs.cpSync(path.join(repo, name), path.join(root, name), { recursive: true });
  children.push(spawn(python, ["-c", server, root, model, rm, String(port)], { cwd: repo, env: { ...process.env, PYTHONPATH: repo }, stdio: ["ignore", "ignore", "inherit"] }));
}
const stop = () => children.forEach((child) => child.kill());
module.exports = { prepare, start, stop, repo };
