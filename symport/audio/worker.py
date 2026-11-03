"""Apply resource limits in a separate process before exec, never preexec_fn in HTTP threads."""

import os
import resource
import sys

if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (85, 85))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.execv(sys.argv[1], sys.argv[1:])
