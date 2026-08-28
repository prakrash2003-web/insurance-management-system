from django.test import TestCase
from django.urls import reverse

from insurance.models import Category, Policy
from insurance.tests import make_admin, make_customer


class CustomerAccessTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(category_name="Health")
        self.policy = Policy.objects.create(
            category=self.category, policy_name="Health Plus",
            sum_assurance=500_000, premium=6_000, tenure=1,
        )
        self.user, self.customer = make_customer()

    def test_dashboard_requires_login(self):
        r = self.client.get(reverse("customer-dashboard"))
        self.assertEqual(r.status_code, 302)

    def test_customer_pages_load(self):
        self.client.force_login(self.user)
        for name in ["customer-dashboard", "customer-profile", "customer-profile-edit",
                     "policy-list", "policy-compare", "history", "renewals",
                     "ask-question", "question-history", "claim-list", "claim-create",
                     "recommendations"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_policy_detail_and_search(self):
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(reverse("policy-detail", args=[self.policy.pk])).status_code, 200
        )
        r = self.client.get(reverse("policy-list"), {"q": "health"})
        self.assertContains(r, "Health Plus")
        r = self.client.get(reverse("policy-list"), {"q": "nonexistent"})
        self.assertNotContains(r, "Health Plus")

    def test_staff_cannot_use_customer_area(self):
        self.client.force_login(make_admin())
        self.assertEqual(self.client.get(reverse("customer-dashboard")).status_code, 403)

    def test_profile_edit_updates_without_password(self):
        self.client.force_login(self.user)
        original = self.user.password
        r = self.client.post(reverse("customer-profile-edit"), {
            "first_name": "New", "last_name": "Name", "email": "new@ex.com",
            "address": "5 Ave", "mobile": "+15551234",
        })
        self.assertRedirects(r, reverse("customer-profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.password, original)
