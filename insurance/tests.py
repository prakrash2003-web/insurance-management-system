import os
import subprocess
import sys
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
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


class AdminLoginFlowTests(TestCase):
    """Reproduce the real POST -> /adminlogin -> dashboard flow (not force_login)."""

    PW = "Adm1n-Correct-PW-2024!"

    def setUp(self):
        self.superuser = User.objects.create_superuser("admin", "admin@ex.com", self.PW)
        self.staff = User.objects.create_user("stf", "stf@ex.com", self.PW, is_staff=True)
        self.cust_user, _ = make_customer("normaluser")

    def _post_login(self, username, password, follow=False):
        return self.client.post(
            reverse("adminlogin"),
            {"username": username, "password": password},
            follow=follow,
        )

    def test_authenticate_works_at_python_level(self):
        from django.contrib.auth import authenticate
        self.assertIsNotNone(authenticate(username="admin", password=self.PW))
        self.assertTrue(self.superuser.is_active)
        self.assertTrue(self.superuser.is_staff)
        self.assertTrue(self.superuser.is_superuser)

    def test_superuser_login_sets_session_and_redirects(self):
        r = self._post_login("admin", self.PW)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and
                         r.context["form"].errors)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.superuser.pk)

    def test_superuser_login_lands_on_admin_dashboard(self):
        r = self._post_login("admin", self.PW, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.redirect_chain[-1][0], reverse("admin-dashboard"))

    def test_staff_login_lands_on_admin_dashboard(self):
        r = self._post_login("stf", self.PW, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.redirect_chain[-1][0], reverse("admin-dashboard"))

    def test_wrong_password_is_rejected(self):
        r = self._post_login("admin", "definitely-not-it")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_after_login_admin_pages_load(self):
        self._post_login("admin", self.PW)
        self.assertEqual(self.client.get(reverse("admin-view-policy")).status_code, 200)

    def test_django_admin_login_also_works(self):
        r = self.client.post("/admin/login/",
                             {"username": "admin", "password": self.PW, "next": "/admin/"},
                             follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_form_renders_csrf_and_correct_field_names(self):
        import re
        body = self.client.get(reverse("adminlogin")).content.decode()
        self.assertIn('name="csrfmiddlewaretoken"', body)
        names = set(re.findall(r'<input[^>]*\bname="([^"]+)"', body))
        self.assertIn("username", names)
        self.assertIn("password", names)

    def test_login_with_csrf_enforced_client(self):
        import re
        from django.test import Client
        csrf_client = Client(enforce_csrf_checks=True)
        page = csrf_client.get(reverse("adminlogin"))
        token = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()
        ).group(1)
        r = csrf_client.post(
            reverse("adminlogin"),
            {"username": "admin", "password": self.PW, "csrfmiddlewaretoken": token},
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.redirect_chain[-1][0], reverse("admin-dashboard"))
        self.assertIn("_auth_user_id", csrf_client.session)

    def test_non_staff_rejected_at_admin_login_form(self):
        # A customer's correct password is not enough: the admin login form
        # requires is_staff (same rule as Django's /admin/).
        r = self._post_login("normaluser", "Str0ngPass!23")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_staff_cannot_log_in(self):
        self.staff.is_active = False
        self.staff.save()
        r = self._post_login("stf", self.PW)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_home_does_not_loop_for_roleless_authenticated_user(self):
        roleless = User.objects.create_user("noroleuser", "n@ex.com", self.PW)
        self.client.force_login(roleless)
        r = self.client.get(reverse("home"))          # must not 302 -> afterlogin -> home ...
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get(reverse("afterlogin"), follow=True)
        self.assertLessEqual(len(r2.redirect_chain), 2)
        self.assertEqual(r2.status_code, 200)

    def test_logout_clears_session(self):
        self._post_login("admin", self.PW)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)


class CheckLoginCommandTests(TestCase):
    def _run(self, **kwargs):
        out = StringIO()
        call_command("check_login", stdout=out, stderr=out, **kwargs)
        return out.getvalue()

    def test_reports_valid_admin_credentials_without_printing_password(self):
        User.objects.create_superuser("adm", "adm@ex.com", "Right-PW-123!")
        text = self._run(username="adm", password="Right-PW-123!")
        self.assertNotIn("Right-PW-123!", text)
        self.assertIn("password matches    : True", text)
        self.assertIn("authenticate()      : True", text)
        self.assertIn("valid for the admin login", text)

    def test_reports_wrong_password(self):
        User.objects.create_superuser("adm", "adm@ex.com", "Right-PW-123!")
        text = self._run(username="adm", password="wrong-one")
        self.assertIn("password matches    : False", text)
        self.assertIn("does NOT match", text)

    def test_reports_missing_user(self):
        text = self._run(username="ghost", password="whatever")
        self.assertIn("user exists         : False", text)


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


class InitSuperuserCommandTests(TestCase):
    _KEYS = ("DJANGO_SUPERUSER_USERNAME", "DJANGO_SUPERUSER_PASSWORD",
             "DJANGO_SUPERUSER_EMAIL")

    def _run(self, *args, **env):
        base = {k: "" for k in self._KEYS}  # start from a clean slate
        base.update(env)
        out, err = StringIO(), StringIO()
        with mock.patch.dict("os.environ", base, clear=False):
            call_command("init_superuser", *args, stdout=out, stderr=err)
        return out.getvalue() + err.getvalue()

    def test_noop_without_env_vars(self):
        output = self._run()
        self.assertIn("skipping", output)
        self.assertFalse(User.objects.filter(is_superuser=True).exists())

    def test_creates_superuser_from_env(self):
        output = self._run(
            DJANGO_SUPERUSER_USERNAME="opsadmin",
            DJANGO_SUPERUSER_EMAIL="ops@example.com",
            DJANGO_SUPERUSER_PASSWORD="a-strong-secret-pw-1234",
        )
        self.assertNotIn("a-strong-secret-pw-1234", output)  # never logs the password
        u = User.objects.get(username="opsadmin")
        self.assertTrue(u.is_superuser and u.is_staff and u.is_active)
        self.assertTrue(u.check_password("a-strong-secret-pw-1234"))
        self.assertEqual(u.email, "ops@example.com")

    def test_idempotent_and_does_not_change_existing_password(self):
        User.objects.create_superuser("opsadmin", "ops@example.com", "original-pw-1234")
        output = self._run(
            DJANGO_SUPERUSER_USERNAME="opsadmin",
            DJANGO_SUPERUSER_PASSWORD="attempted-new-pw-9999",
        )
        self.assertIn("already exists", output)
        u = User.objects.get(username="opsadmin")
        self.assertTrue(u.check_password("original-pw-1234"))
        self.assertFalse(u.check_password("attempted-new-pw-9999"))
        self.assertEqual(User.objects.filter(username="opsadmin").count(), 1)

    def test_force_resets_password_and_regrants_flags(self):
        u = User.objects.create_user("opsadmin", "ops@example.com", "original-pw-1234")
        u.is_staff = u.is_superuser = False
        u.is_active = False
        u.save()
        output = self._run(
            "--force",
            DJANGO_SUPERUSER_USERNAME="opsadmin",
            DJANGO_SUPERUSER_PASSWORD="recovered-pw-5678",
        )
        self.assertNotIn("recovered-pw-5678", output)
        u.refresh_from_db()
        self.assertTrue(u.check_password("recovered-pw-5678"))
        self.assertFalse(u.check_password("original-pw-1234"))
        self.assertTrue(u.is_staff and u.is_superuser and u.is_active)
        self.assertEqual(User.objects.filter(username="opsadmin").count(), 1)

    def test_force_creates_when_missing(self):
        output = self._run(
            "--force",
            DJANGO_SUPERUSER_USERNAME="opsadmin",
            DJANGO_SUPERUSER_PASSWORD="fresh-pw-0000",
        )
        self.assertNotIn("fresh-pw-0000", output)
        u = User.objects.get(username="opsadmin")
        self.assertTrue(u.is_superuser and u.is_staff and u.is_active)


class CheckSuperusersCommandTests(TestCase):
    def test_reports_superuser_without_leaking_secrets(self):
        User.objects.create_superuser("boss", "boss@example.com", "sekret-pw-2468")
        out = StringIO()
        call_command("check_superusers", stdout=out)
        text = out.getvalue()
        self.assertIn("'boss'", text)
        self.assertIn("is_superuser=True", text)
        self.assertNotIn("sekret-pw-2468", text)
        self.assertNotIn("pbkdf2", text)  # no password hash
        self.assertIn("usable superuser exists", text)

    def test_reports_when_no_superuser(self):
        out = StringIO()
        call_command("check_superusers", stdout=out)
        self.assertIn("No superusers found", out.getvalue())


class CheckHostsCommandTests(TestCase):
    def test_prints_resolved_config_without_secrets(self):
        out = StringIO()
        call_command("check_hosts", stdout=out)
        text = out.getvalue()
        self.assertIn("ALLOWED_HOSTS", text)
        self.assertIn("CSRF_TRUSTED_ORIGINS", text)
        self.assertIn("SECURE_PROXY_SSL_HEADER", text)
        self.assertNotIn("SECRET_KEY", text)
        self.assertNotIn("DATABASE_URL", text)


class RailwayHostResolutionTests(TestCase):
    """settings.py resolves ALLOWED_HOSTS at import time, so exercise it in a
    fresh subprocess with a simulated Railway environment."""

    def _allowed_hosts_line(self, extra_env):
        env = {**os.environ, "DJANGO_DEBUG": "False",
               "DJANGO_SECRET_KEY": "t" * 50,
               "DATABASE_URL": "sqlite:///:memory:"}
        env.pop("RAILWAY_ENVIRONMENT_NAME", None)
        env.update(extra_env)
        proc = subprocess.run(
            [sys.executable, "manage.py", "check_hosts"],
            capture_output=True, text=True, env=env, cwd=str(settings.BASE_DIR),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for line in proc.stdout.splitlines():
            if line.strip().startswith("ALLOWED_HOSTS"):
                return line
        self.fail("ALLOWED_HOSTS not found in output")

    def test_railway_domains_always_trusted_even_with_stale_explicit_host(self):
        line = self._allowed_hosts_line({
            "RAILWAY_ENVIRONMENT_NAME": "production",
            "DJANGO_ALLOWED_HOSTS": "a-stale-old-domain.up.railway.app",
        })
        self.assertIn("'.up.railway.app'", line)                 # unconditional
        self.assertIn("'a-stale-old-domain.up.railway.app'", line)  # explicit kept

    def test_railway_suffix_not_added_off_railway(self):
        line = self._allowed_hosts_line({"DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost"})
        self.assertNotIn("railway", line)
