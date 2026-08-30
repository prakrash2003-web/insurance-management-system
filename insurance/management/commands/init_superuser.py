"""Create (or repair) the Django superuser from environment variables.

Designed for a managed host (Railway, etc.) where there is no reliable
interactive shell. It reads:

    DJANGO_SUPERUSER_USERNAME   (required to do anything)
    DJANGO_SUPERUSER_PASSWORD   (required to do anything)
    DJANGO_SUPERUSER_EMAIL      (optional)

Behaviour:

* No-op (exit 0) when the username/password variables are not set - so it is
  safe to leave in the production start command permanently.
* Default: idempotent. If a user with that username already exists, nothing
  changes (the password is NOT touched).
* ``--force``: recovery mode. If the user exists, reset its password from
  DJANGO_SUPERUSER_PASSWORD and (re)grant is_staff / is_superuser / is_active.
  Use this to regain admin access if the password was lost.
* Never prints the password, and never raises: a failure here must not take
  the web process down. Check the logs if it reports a problem.

    python manage.py init_superuser            # create if missing
    python manage.py init_superuser --force     # also repair an existing user
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or repair the superuser from DJANGO_SUPERUSER_* env vars."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="If the user exists, reset its password and re-grant admin flags.",
        )

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        force = options["force"]

        if not username or not password:
            self.stdout.write(
                "init_superuser: DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD "
                "not set - skipping."
            )
            return

        User = get_user_model()
        username_field = User.USERNAME_FIELD

        try:
            user = User.objects.filter(**{username_field: username}).first()

            if user is None:
                User.objects.create_superuser(
                    **{username_field: username}, email=email, password=password
                )
                self.stdout.write(
                    self.style.SUCCESS(f"init_superuser: created superuser {username!r}.")
                )
                return

            if not force:
                self.stdout.write(
                    f"init_superuser: user {username!r} already exists - no changes "
                    f"(use --force to reset its password / admin flags)."
                )
                return

            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            if email:
                user.email = email
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"init_superuser: reset password and admin flags for {username!r}."
                )
            )
        except Exception as exc:  # noqa: BLE001 - must never break the deploy
            self.stderr.write(
                f"init_superuser: could not create/repair superuser "
                f"({type(exc).__name__}: {exc})."
            )
