"""Safely check whether a username + password would authenticate.

Answers "why are my correct credentials rejected?" without ever printing the
password. Prints only booleans and account flags.

The password is taken from --password, or from the DJANGO_SUPERUSER_PASSWORD
environment variable (so it never appears in shell history / process args).

    railway ssh
    python manage.py check_login --username admin
    # (reads DJANGO_SUPERUSER_PASSWORD)
"""

import getpass
import os

from django.contrib.auth import authenticate, get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Report whether a username/password authenticates (no secrets printed)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument(
            "--password",
            help="Password to test. Defaults to $DJANGO_SUPERUSER_PASSWORD, "
            "then an interactive prompt.",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"] or os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not password:
            try:
                password = getpass.getpass("Password to test (not echoed): ")
            except (EOFError, KeyboardInterrupt):
                raise CommandError("No password supplied.")
        if not password:
            raise CommandError("No password supplied.")

        User = get_user_model()
        user = User.objects.filter(**{User.USERNAME_FIELD: username}).first()

        self.stdout.write(f"username            : {username!r}")
        self.stdout.write(f"user exists         : {user is not None}")
        if user is None:
            self.stdout.write(self.style.WARNING(
                "  -> no such user. Create/repair it with:\n"
                "     DJANGO_SUPERUSER_USERNAME / _PASSWORD set, then "
                "`python manage.py init_superuser --force`"
            ))
            return

        self.stdout.write(f"is_active           : {user.is_active}")
        self.stdout.write(f"is_staff            : {user.is_staff}")
        self.stdout.write(f"is_superuser        : {user.is_superuser}")
        self.stdout.write(f"has usable password : {user.has_usable_password()}")
        self.stdout.write(f"password matches    : {user.check_password(password)}")

        authed = authenticate(username=username, password=password)
        self.stdout.write(f"authenticate()      : {authed is not None}")
        self.stdout.write(
            f"accepted at /adminlogin : {authed is not None and user.is_staff}"
        )

        self.stdout.write("\n== Verdict ==")
        if authed is not None and user.is_staff:
            self.stdout.write(self.style.SUCCESS(
                "  These credentials are valid for the admin login. If the browser\n"
                "  still fails, the issue is the session cookie (e.g. DEBUG=False +\n"
                "  plain HTTP, or the browser blocking cookies), not the password."
            ))
        elif authed is not None and not user.is_staff:
            self.stdout.write(self.style.WARNING(
                "  Password is correct but the account is not staff. Run\n"
                "  `python manage.py init_superuser --force` with the env vars set."
            ))
        elif user.check_password(password):
            self.stdout.write(self.style.WARNING(
                "  Password is correct but the account is inactive (is_active=False).\n"
                "  Run `python manage.py init_superuser --force`."
            ))
        else:
            self.stdout.write(self.style.ERROR(
                "  The password does NOT match what is stored. Reset it:\n"
                "  set DJANGO_SUPERUSER_USERNAME / _PASSWORD, then\n"
                "  `python manage.py init_superuser --force`."
            ))
