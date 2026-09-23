"""Architectural guard.

Hexagonal architecture holds only while the core stays ignorant of the outside
world. This test fails the moment someone imports FastAPI, SQLAlchemy or an
HTTP client into app/domain -- which is much easier to do by accident than to
notice in review.
"""

import subprocess
import sys
from pathlib import Path

FORBIDDEN = [
    "fastapi",
    "starlette",
    "sqlalchemy",
    "asyncpg",
    "alembic",
    "pydantic",
    "requests",
    "openmeteo_requests",
    "pandas",
    "numpy",
]

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"


def test_domain_imports_no_framework():
    """Import the whole domain in a clean interpreter and inspect sys.modules."""
    modules = [f"app.domain.{p.stem}" for p in DOMAIN.glob("*.py") if p.stem != "__init__"]
    script = (
        "import importlib, sys\n"
        f"for m in {modules!r}: importlib.import_module(m)\n"
        f"print([b for b in {FORBIDDEN!r} if b in sys.modules])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=DOMAIN.parents[1],
        check=True,
    )
    leaked = result.stdout.strip()
    assert leaked == "[]", f"domain leaked framework imports: {leaked}"


def test_domain_source_has_no_outward_imports():
    """Cheap static backstop for imports hidden inside functions."""
    offenders = []
    for path in DOMAIN.glob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            if any(f"{pkg}" in stripped.split() or f"{pkg}." in stripped for pkg in FORBIDDEN):
                offenders.append(f"{path.name}:{lineno}: {stripped}")
    assert not offenders, "outward imports in domain:\n" + "\n".join(offenders)
