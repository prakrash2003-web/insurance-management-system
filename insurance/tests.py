from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from customer.models import Customer
from insurance.models import Category, Claim, Notification, Policy, PolicyRecord
from insurance.permissions import CUSTOMER_GROUP
from insurance.services import calculate_premium, recommend_policies


def make_customer(username="cust", password="Str0ngPass!23"):
    user = User.objects.create_user(username, f"{username}@ex.com", password,
                                    first_name="Cy", last_name="Doe")
    group, _ = Group.objects.get_or_create(name=CUSTOMER_GROUP)
    user.groups.add(group)
    customer = Customer.objects.create(user=user, address="1 St", mobile="+15550100")
    return user, customer


def make_admin(username="boss", password="Str0ngPass!23"):
    return User.objects.create_user(username, f"{username}@ex.com", password, is_staff=True)


class BaseData(TestCase):
    def setUp(self):
        self.category = Category.objects.create(category_name="Life")
        self.policy = Policy.objects.create(
            category=self.category, policy_name="Term Life",
            sum_assurance=1_000_000, premium=10_000, tenure=20,
        )
        self.cust_user, self.customer = make_customer()
        self.admin_user = make_admin()


class PermissionTests(BaseData):
    def test_anonymous_redirected_from_admin(self):
        r = self.client.get(reverse("admin-view-policy"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("adminlogin", r.url)

    def test_customer_forbidden_from_admin_crud(self):
        self.client.force_login(self.cust_user)
        for name in ["admin-dashboard", "admin-view-customer", "admin-view-policy",
                     "admin-add-category", "admin-claims"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_customer_cannot_delete_customer(self):
        self.client.force_login(self.cust_user)
        r = self.client.post(reverse("delete-customer", args=[self.customer.pk]))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())

    def test_staff_can_reach_admin(self):
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get(reverse("admin-dashboard")).status_code, 200)

    def test_afterlogin_routes_by_role(self):
        self.client.force_login(self.admin_user)
        self.assertRedirects(self.client.get(reverse("afterlogin")),
                             reverse("admin-dashboard"))
        self.client.force_login(self.cust_user)
        self.assertRedirects(self.client.get(reverse("afterlogin")),
                             reverse("customer-dashboard"))


class AuthTests(TestCase):
    def test_signup_creates_customer_in_group(self):
        r = self.client.post(reverse("customersignup"), {
            "first_name": "A", "last_name": "B", "username": "newbie",
            "email": "newbie@ex.com", "password": "Str0ngPass!23",
            "address": "2 Rd", "mobile": "+15550111",
        })
        self.assertRedirects(r, reverse("customerlogin"))
        user = User.objects.get(username="newbie")
        self.assertTrue(user.groups.filter(name=CUSTOMER_GROUP).exists())
        self.assertTrue(hasattr(user, "customer"))
        self.assertTrue(user.check_password("Str0ngPass!23"))

    def test_signup_rejects_weak_password(self):
        r = self.client.post(reverse("customersignup"), {
            "first_name": "A", "last_name": "B", "username": "weak",
            "email": "weak@ex.com", "password": "123",
            "address": "2 Rd", "mobile": "+15550111",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="weak").exists())

    def test_login(self):
        make_customer("logintest")
        r = self.client.post(reverse("customerlogin"),
                             {"username": "logintest", "password": "Str0ngPass!23"})
        self.assertEqual(r.status_code, 302)


class PolicyAdminTests(BaseData):
    def test_admin_creates_policy_with_category(self):
        self.client.force_login(self.admin_user)
        r = self.client.post(reverse("admin-add-policy"), {
            "category": self.category.pk, "policy_name": "New Plan",
            "sum_assurance": 500000, "premium": 4000, "tenure": 10,
            "is_active": "on",
        })
        self.assertRedirects(r, reverse("admin-view-policy"))
        self.assertTrue(Policy.objects.filter(policy_name="New Plan").exists())

    def test_policy_rejects_premium_above_sum(self):
        self.client.force_login(self.admin_user)
        r = self.client.post(reverse("admin-add-policy"), {
            "category": self.category.pk, "policy_name": "Bad",
            "sum_assurance": 1000, "premium": 5000, "tenure": 10,
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Policy.objects.filter(policy_name="Bad").exists())


class ApplicationTests(BaseData):
    def test_apply_requires_post(self):
        self.client.force_login(self.cust_user)
        self.assertEqual(
            self.client.get(reverse("apply", args=[self.policy.pk])).status_code, 405
        )

    def test_apply_creates_record_once(self):
        self.client.force_login(self.cust_user)
        self.client.post(reverse("apply", args=[self.policy.pk]))
        self.client.post(reverse("apply", args=[self.policy.pk]))
        self.assertEqual(
            PolicyRecord.objects.filter(customer=self.customer, policy=self.policy).count(), 1
        )
        self.assertTrue(Notification.objects.filter(user=self.cust_user).exists())

    def test_approve_requires_post_and_sets_dates(self):
        record = PolicyRecord.objects.create(customer=self.customer, policy=self.policy)
        self.client.force_login(self.admin_user)
        self.assertEqual(
            self.client.get(reverse("approve-request", args=[record.pk])).status_code, 405
        )
        self.client.post(reverse("approve-request", args=[record.pk]))
        record.refresh_from_db()
        self.assertEqual(record.status, PolicyRecord.Status.APPROVED)
        self.assertIsNotNone(record.start_date)
        self.assertIsNotNone(record.end_date)
        self.assertTrue(
            Notification.objects.filter(user=self.cust_user, kind="success").exists()
        )

    def test_reject_sets_status(self):
        record = PolicyRecord.objects.create(customer=self.customer, policy=self.policy)
        self.client.force_login(self.admin_user)
        self.client.post(reverse("reject-request", args=[record.pk]))
        record.refresh_from_db()
        self.assertEqual(record.status, PolicyRecord.Status.DISAPPROVED)

    def test_customer_cannot_approve(self):
        record = PolicyRecord.objects.create(customer=self.customer, policy=self.policy)
        self.client.force_login(self.cust_user)
        self.assertEqual(
            self.client.post(reverse("approve-request", args=[record.pk])).status_code, 403
        )


class ClaimTests(BaseData):
    def setUp(self):
        super().setUp()
        self.record = PolicyRecord.objects.create(
            customer=self.customer, policy=self.policy,
            status=PolicyRecord.Status.APPROVED,
        )

    def test_customer_files_claim(self):
        self.client.force_login(self.cust_user)
        r = self.client.post(reverse("claim-create"), {
            "policy_record": self.record.pk, "claim_amount": "5000",
            "description": "Accident",
        })
        self.assertRedirects(r, reverse("claim-list"))
        self.assertEqual(Claim.objects.filter(customer=self.customer).count(), 1)

    def test_claim_amount_capped_at_sum_assured(self):
        self.client.force_login(self.cust_user)
        r = self.client.post(reverse("claim-create"), {
            "policy_record": self.record.pk, "claim_amount": "99999999",
            "description": "Too big",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Claim.objects.count(), 0)

    def test_admin_reviews_claim_and_notifies(self):
        claim = Claim.objects.create(
            customer=self.customer, policy_record=self.record,
            claim_amount=Decimal("5000"), description="x",
        )
        self.client.force_login(self.admin_user)
        r = self.client.post(reverse("admin-claim-detail", args=[claim.pk]),
                             {"status": "Approved", "admin_remarks": "ok"})
        self.assertRedirects(r, reverse("admin-claims"))
        claim.refresh_from_db()
        self.assertEqual(claim.status, "Approved")
        self.assertTrue(Notification.objects.filter(user=self.cust_user).exists())

    def test_customer_cannot_see_others_claim(self):
        other_user, other_cust = make_customer("other")
        claim = Claim.objects.create(
            customer=other_cust, policy_record=self.record,
            claim_amount=Decimal("100"), description="x",
        )
        self.client.force_login(self.cust_user)
        self.assertEqual(
            self.client.get(reverse("claim-detail", args=[claim.pk])).status_code, 404
        )


class AdminCustomerUpdateTests(BaseData):
    def test_update_does_not_change_password(self):
        original_hash = self.cust_user.password
        self.client.force_login(self.admin_user)
        r = self.client.post(reverse("update-customer", args=[self.customer.pk]), {
            "first_name": "Changed", "last_name": "Name",
            "email": "changed@ex.com", "is_active": "on",
            "address": "9 New Rd", "mobile": "+15559999",
        })
        self.assertRedirects(r, reverse("admin-view-customer"))
        self.cust_user.refresh_from_db()
        self.assertEqual(self.cust_user.first_name, "Changed")
        self.assertEqual(self.cust_user.password, original_hash)
        self.assertTrue(self.cust_user.check_password("Str0ngPass!23"))


class ServiceTests(TestCase):
    def test_premium_calculator_breakdown(self):
        result = calculate_premium(age=30, sum_assured=1_000_000, tenure=20, smoker=False)
        self.assertGreater(result["estimated_annual_premium"], 0)
        self.assertEqual(len(result["breakdown"]), 5)
        smoker = calculate_premium(age=30, sum_assured=1_000_000, tenure=20, smoker=True)
        self.assertGreater(
            smoker["estimated_annual_premium"], result["estimated_annual_premium"]
        )

    def test_recommendation_scores_and_explains(self):
        cat = Category.objects.create(category_name="Life")
        good = Policy.objects.create(category=cat, policy_name="Fits", sum_assurance=1_000_000,
                                     premium=8_000, tenure=20)
        Policy.objects.create(category=cat, policy_name="TooPricey", sum_assurance=1_000_000,
                              premium=900_000, tenure=1)
        recs = recommend_policies(
            Policy.objects.all(), age=30, annual_income=100_000,
            dependents=2, desired_coverage=1_000_000,
        )
        self.assertTrue(recs)
        self.assertEqual(recs[0].policy, good)
        self.assertTrue(recs[0].reasons)
        self.assertGreaterEqual(recs[0].score, recs[-1].score)


class RenewalTests(BaseData):
    def test_renewal_status_transitions(self):
        from datetime import timedelta

        from django.utils import timezone

        record = PolicyRecord.objects.create(
            customer=self.customer, policy=self.policy,
            status=PolicyRecord.Status.APPROVED,
            start_date=timezone.now().date() - timedelta(days=800),
            end_date=timezone.now().date() - timedelta(days=1),
        )
        self.assertEqual(record.renewal_status, PolicyRecord.RenewalStatus.EXPIRED)
        record.end_date = timezone.now().date() + timedelta(days=10)
        self.assertEqual(record.renewal_status, PolicyRecord.RenewalStatus.DUE)

    def test_customer_can_renew(self):
        from datetime import timedelta

        from django.utils import timezone

        record = PolicyRecord.objects.create(
            customer=self.customer, policy=self.policy,
            status=PolicyRecord.Status.APPROVED,
            start_date=timezone.now().date() - timedelta(days=400),
            end_date=timezone.now().date() + timedelta(days=5),
        )
        self.client.force_login(self.cust_user)
        old_end = record.end_date
        r = self.client.post(reverse("renew", args=[record.pk]))
        self.assertRedirects(r, reverse("renewals"))
        record.refresh_from_db()
        self.assertGreater(record.end_date, old_end)


class ErrorPageTests(BaseData):
    def test_custom_403_page(self):
        self.client.force_login(self.cust_user)
        r = self.client.get(reverse("admin-dashboard"))
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "Access denied", status_code=403)

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_custom_404_page(self):
        r = self.client.get("/no-such-page-here")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "Page not found", status_code=404)

    def test_favicon_redirects_to_static(self):
        r = self.client.get("/favicon.ico")
        self.assertEqual(r.status_code, 301)
        self.assertTrue(r.url.endswith("/static/favicon.svg"))
