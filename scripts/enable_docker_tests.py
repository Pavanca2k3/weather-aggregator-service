"""Make docker-py usable in this environment, so Testcontainers can run.

The problem: `niquests` (pulled in by the openmeteo-requests SDK) depends on
`urllib3-future`, which installs a `urllib3_future.pth` that *replaces* the real
`urllib3` package at interpreter start. docker-py's transport subclasses urllib3
internals and breaks against that fork -- on Windows named pipes it fails with
"'NpipeSocket' object has no attribute 'type'", so Testcontainers cannot reach
Docker and every integration test skips.

The fix has two parts, and one alone is not enough: the .pth does not merely
alias the name, it rewrites the contents of the `urllib3/` directory at every
interpreter start. So the override is disabled AND genuine urllib3 is
reinstalled over what the fork left behind.

`niquests` imports `urllib3_future` directly rather than through the alias, so
the Open-Meteo SDK keeps working -- verified against the live API.

This must be re-run after any `pip install -r requirements-dev.txt`, because
reinstalling urllib3-future restores the .pth file. Running it is safe and
idempotent.

    python scripts/enable_docker_tests.py           # disable the override
    python scripts/enable_docker_tests.py --revert  # put it back
"""

import argparse
import subprocess
import sys
import sysconfig
from pathlib import Path

PTH_NAME = "urllib3_future.pth"
DISABLED_SUFFIX = ".disabled"
GENUINE_URLLIB3 = "2.8.0"


def site_packages() -> Path:
    return Path(sysconfig.get_paths()["purelib"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revert", action="store_true", help="restore the override")
    args = parser.parse_args()

    packages = site_packages()
    active = packages / PTH_NAME
    disabled = packages / (PTH_NAME + DISABLED_SUFFIX)

    if args.revert:
        if disabled.exists():
            disabled.rename(active)
            print(f"restored {active.name}: urllib3 is the urllib3-future fork again")
        else:
            print("nothing to restore")
        return 0

    if active.exists():
        active.rename(disabled)
        print(f"disabled {active.name}")
    elif disabled.exists():
        print(f"{PTH_NAME} already disabled")
    else:
        print("urllib3-future override not found -- nothing to do")
        return 0

    # Disabling the .pth is not sufficient on its own: the fork has already
    # overwritten the urllib3 package directory, so genuine urllib3 has to be
    # laid back down over it.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--ignore-installed",
            f"urllib3=={GENUINE_URLLIB3}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout[-2000:], file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        return 1

    check = subprocess.run(
        [sys.executable, "-c", "import urllib3; print(urllib3.__version__)"],
        capture_output=True,
        text=True,
    )
    version = check.stdout.strip()
    print(f"urllib3 in use: {version}")
    if version != GENUINE_URLLIB3:
        print(
            f"warning: expected urllib3 {GENUINE_URLLIB3}; Docker tests will still skip",
            file=sys.stderr,
        )
        return 1
    print("docker-py can now reach Docker; Testcontainers tests will run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
