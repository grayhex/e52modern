# Installation

For normal use, follow [Docker deployment](DOCKER_DEPLOYMENT.md) and
[Windows Bridge](WINDOWS_BRIDGE.md). Linux/macOS: `tools/install.sh`; Windows:
`./tools/install.ps1` from PowerShell with Docker Desktop using Linux containers.

## Python development

Python 3.11+, a C++ compiler for legacy theme tools, and FFmpeg for audio:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,theme,media,transport-discovery]'
python -m symport.web --port 8765
pytest
```

On Debian/Ubuntu install `g++ ffmpeg`; native Gammu bindings may additionally need
`libgammu-dev pkg-config`, or use the published python-gammu wheel. Host USB/Bluetooth
permissions and Nokia drivers are separate from installing Python dependencies.

For application builds use the external `symbian-platform` toolchain; see
[DEVELOPMENT.md](DEVELOPMENT.md), [APPLICATIONS.md](APPLICATIONS.md) and the pinned
SDK verification recipe in `tools/sdk/`. Official MakeSIS/SignSIS remain external
programs; configure their paths without adding binaries or private keys to Git.

EKA2L1 is supplied by the optional MGO Compose service. User ROM/firmware goes into
its persistent data volume through Emulator Lab, never into an image or source tree.
Do not use WSL USB passthrough as a substitute for the Windows Bridge unless you
intend to maintain those host drivers and permissions yourself.
