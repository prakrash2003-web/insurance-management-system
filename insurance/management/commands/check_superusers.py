"""Read-only production diagnostic for admin access.

Reports which database the app is connected to and which superusers exist,
**without printing any secret** (no password hashes, no DATABASE_URL, no keys).

Run inside the deployed environment::

    python manage.py check_superusers
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Show the connected database and existing superusers (no secrets printed)."

    def handle(self, *args, **options):
        from django.conf import settings

        vendor = connection.vendor  # 'postgresql' | 'sqlite' | ...
        db_name = connection.settings_dict.get("NAME", "")
        if vendor == "sqlite":
            db_name = os.path.basename(str(db_name)) or "(memory)"
        on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT_NAME"))

        self.stdout.write("== Environment ==")
        self.stdout.write(f"  DEBUG                 : {settings.DEBUG}")
        self.stdout.write(f"  RAILWAY_ENVIRONMENT   : {os.environ.get('RAILWAY_ENVIRONMENT_NAME', '(not set)')}")
        self.stdout.write(f"  DATABASE_URL          : {'PRESENT' if os.environ.get('DATABASE_URL', '').strip() else 'MISSING'}")
        self.stdout.write(f"  DB backend            : {vendor}")
        self.stdout.write(f"  DB name (no creds)    : {db_name}")

        if on_railway and vendor == "sqlite":
            self.stdout.write(self.style.ERROR(
                "\n  !! On Railway but using SQLite. The container filesystem is\n"
                "     ephemeral, so this database (and any superuser in it) is wiped\n"
                "     on every deploy. Set DATABASE_URL to ${{Postgres.DATABASE_URL}}."
            ))

        User = get_user_model()
        supers = User.objects.filter(is_superuser=True).order_by("date_joined")
        self.stdout.write(f"\n== Users ==  (total: {User.objects.count()})")
        if not supers:
            self.stdout.write(self.style.WARNING("  No superusers found."))
        for u in supers:
            self.stdout.write(
                f"  - {u.get_username()!r}: is_superuser={u.is_superuser} "
                f"is_staff={u.is_staff} is_active={u.is_active} "
                f"usable_password={u.has_usable_password()} "
                f"last_login={u.last_login.isoformat() if u.last_login else 'never'}"
            )

        self.stdout.write("\n== Verdict ==")
        healthy = supers.filter(is_staff=True, is_active=True).exists()
        if healthy:
            self.stdout.write(self.style.SUCCESS(
                "  A usable superuser exists in the connected database."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "  No usable superuser in the connected database - run:\n"
                "    python manage.py init_superuser --force\n"
                "  with DJANGO_SUPERUSER_USERNAME / _PASSWORD (and _EMAIL) set."
            ))
        if on_railway and vendor == "sqlite":
            self.stdout.write(self.style.ERROR(
                "  The connected database is ephemeral SQLite (see warning above) - "
                "fix DATABASE_URL first, then re-check."
            ))
