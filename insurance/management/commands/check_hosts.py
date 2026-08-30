"""Read-only diagnostic for the ALLOWED_HOSTS / CSRF / proxy configuration.

Everything printed is a hostname or a boolean - no secrets (no SECRET_KEY,
no DATABASE_URL, no passwords).

Run inside the deployed environment::

    python manage.py check_hosts
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand

_HOST_ENV_VARS = [
    "RAILWAY_ENVIRONMENT_NAME",
    "RAILWAY_PUBLIC_DOMAIN",
    "RAILWAY_PRIVATE_DOMAIN",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_SECURE_SSL_REDIRECT",
]


class Command(BaseCommand):
    help = "Show the resolved host/CSRF/proxy settings and the raw Railway host vars."

    def handle(self, *args, **options):
        self.stdout.write("== Resolved settings ==")
        self.stdout.write(f"  DEBUG                  : {settings.DEBUG}")
        self.stdout.write(f"  ALLOWED_HOSTS          : {settings.ALLOWED_HOSTS}")
        self.stdout.write(f"  CSRF_TRUSTED_ORIGINS   : {settings.CSRF_TRUSTED_ORIGINS}")
        self.stdout.write(
            f"  SECURE_SSL_REDIRECT    : {getattr(settings, 'SECURE_SSL_REDIRECT', '(unset)')}"
        )
        self.stdout.write(
            f"  SECURE_PROXY_SSL_HEADER: {getattr(settings, 'SECURE_PROXY_SSL_HEADER', '(unset)')}"
        )

        self.stdout.write("\n== Raw environment (hostnames only, no secrets) ==")
        for name in _HOST_ENV_VARS:
            value = os.environ.get(name)
            self.stdout.write(f"  {name:28}: {value!r}" if value is not None
                              else f"  {name:28}: (not set)")

        self.stdout.write("\n== How to read this ==")
        self.stdout.write(
            "  The hostname in your browser's address bar must match one entry in\n"
            "  ALLOWED_HOSTS. A leading dot (e.g. '.up.railway.app') matches any\n"
            "  sub-domain. If it does not match, every request returns HTTP 400\n"
            "  (DisallowedHost) - check the deploy logs for:\n"
            "    Invalid HTTP_HOST header: '<hostname>'. You may need to add ..."
        )
