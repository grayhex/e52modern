"""Print the runtime requirements of the container from pyproject.toml (one per line).

The Dockerfile installs these before copying the sources, so editing application code never
reinstalls the dependencies. Extras listed here must match what the image needs at run time.
"""

import sys
import tomllib

EXTRAS = ("theme", "phone", "media", "transport-discovery")

with open(sys.argv[1] if len(sys.argv) > 1 else "pyproject.toml", "rb") as handle:
    project = tomllib.load(handle)["project"]
requirements = set(project.get("dependencies", []))
for extra in EXTRAS:
    requirements.update(project["optional-dependencies"][extra])
print("\n".join(sorted(requirements)))
