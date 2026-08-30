"""Diagnose whether the environment variables Django needs are actually present.

This script deliberately does NOT import Django settings, so it still runs even
when ``DJANGO_SECRET_KEY`` is missing (importing settings would raise first).

It never prints secret values - only PRESENT / MISSING and lengths.

Usage
-----
Against the linked Railway service + environment, from your machine::

    railway run python scripts/railway_env_check.py

Or inside the Railway service Shell (Dashboard -> service -> ... -> Shell)::

    python scripts/railway_env_check.py
"""

import os

SECRET = {"DJANGO_SECRET_KEY", "DATABASE_URL", "EMAIL_HOST_PASSWORD"}
EXPECTED = [
    "DJANGO_SECRET_KEY",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DATABASE_URL",
    "RAILWAY_PUBLIC_DOMAIN",
    "RAILWAY_ENVIRONMENT_NAME",
    "RAILWAY_SERVICE_NAME",
    "RAILWAY_PROJECT_NAME",
    "PORT",
]


def describe(name):
    raw = os.environ.get(name)
    if raw is None:
        return "MISSING"
    if raw == "":
        return "MISSING (set but empty)"
    if raw.strip() == "":
        return "MISSING (whitespace only)"
    if name in SECRET:
        return f"PRESENT (length {len(raw)})"
    return repr(raw)


print("== Environment seen by the Railway service/deployment ==")
for name in EXPECTED:
    print(f"  {name} = {describe(name)}")

# Detect the classic misconfigurations.
bad_names = sorted(k for k in os.environ if k != k.strip())
if bad_names:
    print("\n  WARNING - variable NAMES with leading/trailing whitespace:")
    for k in bad_names:
        print(f"    {k!r}")

lookalikes = sorted(
    k for k in os.environ
    if k != "DJANGO_SECRET_KEY"
    and ("SECRET" in k.upper() or k.upper().replace("_", "").replace(" ", "") == "DJANGOSECRETKEY")
)
if lookalikes:
    print("\n  NOTE - other keys containing 'SECRET' (possible typo of DJANGO_SECRET_KEY):")
    for k in lookalikes:
        print(f"    {k!r}")

debug = os.environ.get("DJANGO_DEBUG", "")
print(
    "\n== Verdict =="
)
if os.environ.get("DJANGO_SECRET_KEY", "").strip():
    print("  DJANGO_SECRET_KEY = PRESENT for this service/environment")
else:
    print("  DJANGO_SECRET_KEY = MISSING for this service/environment")
print(f"  DJANGO_DEBUG = {debug or 'MISSING (defaults to False)'}")
print(
    "  DATABASE_URL = "
    + ("PRESENT" if os.environ.get("DATABASE_URL", "").strip() else "MISSING")
)
