"""Populate the database with demo data for local exploration.

Usage:  python manage.py seed_demo
Idempotent-ish: it will not create duplicate categories/policies/users.
"""

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction

from customer.models import Customer
from insurance.models import Category, Policy, PolicyRecord
from insurance.permissions import CUSTOMER_GROUP

CATEGORIES = {
    "Life": "Long-term life cover for you and your dependents.",
    "Health": "Hospitalisation and medical expense cover.",
    "Vehicle": "Motor insurance for cars and two-wheelers.",
    "Travel": "Short-term cover for trips abroad.",
}

POLICIES = [
    ("Life", "Term Life Secure", 5_000_000, 12_000, 20),
    ("Life", "Whole Life Plus", 2_500_000, 20_000, 30),
    ("Health", "Family Health Shield", 1_000_000, 15_000, 1),
    ("Health", "Senior Care", 500_000, 22_000, 1),
    ("Vehicle", "Motor Comprehensive", 800_000, 9_000, 1),
    ("Travel", "Global Traveller", 300_000, 2_500, 1),
]


class Command(BaseCommand):
    help = "Create demo categories, policies, an admin and a customer."

    @transaction.atomic
    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name=CUSTOMER_GROUP)

        cats = {}
        for name, desc in CATEGORIES.items():
            cats[name], _ = Category.objects.get_or_create(
                category_name=name, defaults={"description": desc}
            )

        for cat_name, pname, sa, prem, tenure in POLICIES:
            Policy.objects.get_or_create(
                policy_name=pname,
                defaults={
                    "category": cats[cat_name],
                    "sum_assurance": sa,
                    "premium": prem,
                    "tenure": tenure,
                },
            )

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin12345")
            self.stdout.write("Created superuser 'admin' / 'admin12345'")

        if not User.objects.filter(username="customer").exists():
            u = User.objects.create_user(
                "customer", "customer@example.com", "customer12345",
                first_name="Casey", last_name="Rivera",
            )
            u.groups.add(group)
            Customer.objects.create(user=u, address="1 Demo Street", mobile="+15550100")
            self.stdout.write("Created customer 'customer' / 'customer12345'")

        # Give the demo customer one pending application.
        cust = Customer.objects.filter(user__username="customer").first()
        if cust and not cust.policy_records.exists():
            PolicyRecord.objects.create(
                customer=cust, policy=Policy.objects.get(policy_name="Term Life Secure")
            )

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
