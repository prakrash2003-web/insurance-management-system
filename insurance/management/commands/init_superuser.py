"""Create the initial Django superuser from environment variables.

Designed for a managed host (Railway, etc.) where there is no interactive
shell to run ``createsuperuser``. It reads:

    DJANGO_SUPERUSER_USERNAME   (required to do anything)
    DJANGO_SUPERUSER_PASSWORD   (required to do anything)
    DJANGO_SUPERUSER_EMAIL      (optional)

Behaviour:

* No-op (exit 0) when the username/password variables are not set - so it is
  safe to leave in the production start command permanently.
* Idempotent - if a user with that username already exists it changes nothing.
* Never prints the password, and never raises: a failure here must not take
  the web process down. Check the deploy logs if it reports a problem.

Run automatically from ``railway.json`` (after ``migrate``), or manually::

    python manage.py init_superuser
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the initial superuser from DJANGO_SUPERUSER_* env vars (idempotent)."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()

        if not username or not password:
            self.stdout.write(
                "init_superuser: DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD "
                "not set - skipping."
            )
            return

        User = get_user_model()
        username_field = User.USERNAME_FIELD

        try:
            if User.objects.filter(**{username_field: username}).exists():
                self.stdout.write(
                    f"init_superuser: user {username!r} already exists - no changes."
                )
                return

            User.objects.create_superuser(
                **{username_field: username}, email=email, password=password
            )
            self.stdout.write(
                self.style.SUCCESS(f"init_superuser: created superuser {username!r}.")
            )
        except Exception as exc:  # noqa: BLE001 - must never break the deploy
            self.stderr.write(
                f"init_superuser: could not create superuser "
                f"({type(exc).__name__}: {exc})."
            )
