"""Include corresponding project sources, dependency sources and license metadata."""
import hashlib
import importlib.metadata as metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

root = Path(__file__).resolve().parents[2]
out = root / 'build/windows/portable'
source = out / 'sources'
source.mkdir(parents=True, exist_ok=True)
for name in ('symport', 'tools/windows'):
    shutil.copytree(root / name, source / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'), dirs_exist_ok=True)
for name in ('pyproject.toml', 'LICENSE'):
    shutil.copy(root / name, source / name)
shutil.copy(root / 'docs/WINDOWS_BRIDGE.md', out / 'README.md')
licenses = []
for dist in metadata.distributions():
    name = dist.metadata['Name']
    licenses.append({'name': name, 'version': dist.version, 'license': dist.metadata.get('License-Expression') or dist.metadata.get('License')})
    if name.casefold() not in ('python-gammu', 'pystray'):
        continue
    with urlopen(f'https://pypi.org/pypi/{name}/{dist.version}/json') as response:
        project = json.load(response)
    artifact = next(a for a in project['urls'] if a['packagetype'] == 'sdist')
    with urlopen(artifact['url']) as response:
        raw = response.read()
    assert hashlib.sha256(raw).hexdigest() == artifact['digests']['sha256']
    (source / artifact['filename']).write_bytes(raw)
    licenses[-1]['source'] = artifact['url']
    licenses[-1]['sha256'] = artifact['digests']['sha256']
    target = out / 'licenses' / name
    target.mkdir(parents=True, exist_ok=True)
    for file in dist.files or []:
        if any(part.casefold() in ('licenses', 'license', 'copying') for part in file.parts) or file.name.upper().startswith(('LICENSE', 'COPYING')):
            path = Path(dist.locate_file(file))
            if path.is_file():
                shutil.copy(path, target / path.name)
# python-gammu Windows wheels include libGammu; ship its matching source too.
import gammu
version = gammu.Version()[0]
url = f'https://dl.cihar.com/gammu/releases/gammu-{version}.tar.xz'
with urlopen(url) as response:
    raw = response.read()
(source / f'gammu-{version}.tar.xz').write_bytes(raw)
licenses.append({'name': 'libGammu', 'version': version, 'license': 'GPL-2.0-or-later', 'source': url, 'sha256': hashlib.sha256(raw).hexdigest()})
(out / 'DEPENDENCIES.json').write_text(json.dumps(licenses, indent=2), encoding='utf-8')
(out / 'LICENSE.txt').write_text('SymPort source: MIT (sources/LICENSE). This combined Windows distribution includes Gammu/python-gammu (GPL-2.0-or-later) and pystray (LGPL-3.0). Distribution under GPL-3.0-or-later; original dependency notices apply. Corresponding sources and the build recipe are in sources/. No Nokia drivers, proprietary ROM or signing keys are included.\n', encoding='utf-8')
with urlopen('https://www.gnu.org/licenses/gpl-3.0.txt') as response:
    (out / 'GPL-3.0.txt').write_bytes(response.read())
(out / 'SHA256SUMS.txt').write_text(hashlib.sha256((out/'SymPortBridge.exe').read_bytes()).hexdigest() + '  SymPortBridge.exe\n', encoding='ascii')
