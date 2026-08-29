# Insurance Management System

A Django web application that models a small insurance provider. Customers can
browse and compare policies, get a transparent rule-based recommendation, apply
for cover, file claims and renew approved policies. Administrators manage the
policy catalogue and review applications, questions and claims.

---

## Overview

The project began as a basic CRUD demo and has been reworked into a
portfolio-ready application with:

* **Role-based access control** – customers (a `CUSTOMER` group + `Customer`
  profile) and staff/administrators (`is_staff`) are strictly separated. A
  customer can never reach an admin CRUD view; every customer view requires
  login.
* **Environment-based configuration** – no secrets in source. `SECRET_KEY`,
  `DEBUG`, `ALLOWED_HOSTS`, database URL and email settings all come from the
  environment (via a local `.env`).
* **Hardened defaults** – all state-changing operations are `POST` + CSRF
  protected, destructive actions use confirmation dialogs, production security
  settings (HSTS, secure cookies, SSL redirect) switch on automatically when
  `DEBUG=False`.
* **A real automated test suite** – 32 tests (`python manage.py test`).
* **A modern, responsive UI** built with a small hand-written CSS design system
  (no external CDNs) and custom `403` / `404` / `500` pages.

## Features

### Customer
* Dashboard with application / claim / question counts and renewal alerts
* Profile page + edit profile (never touches the password)
* Browse policies with search and category filter, pagination
* Policy detail pages
* Side-by-side policy comparison (2–4 policies)
* **Premium calculator** – estimate an annual premium from age, sum assured,
  tenure, category and smoker status, with a full factor breakdown
* **Rule-based policy recommendation** – scores active policies against age,
  income, dependents and desired coverage and lists the reasons for each result
  (this is *not* machine learning; every number comes from explicit rules)
* Apply for a policy, track application status, view application detail
* **Claims** – file a claim against an approved policy, track status and read
  admin remarks
* **Renewals** – approved policies get start/end dates; renew when due or expired
* Ask questions and read administrator replies
* Change password / password reset flow
* In-app notifications for application and claim events, question replies and
  renewals

### Administrator
* Dashboard statistics (customers, policies, applications by status, claims,
  unanswered questions, total sum assured) with recent-activity tables
* Customer management – search, edit (identity + contact, **no password field**),
  delete with confirmation
* Category management – CRUD with search and policy counts
* Policy management – CRUD with search, category filter, applicant counts,
  active/inactive toggle
* Application management – filter by status, search, approve / reject (POST only,
  sets cover dates, notifies the customer)
* Claim management – filter, review, approve/reject with remarks
* Questions – filter answered/unanswered, reply
* Django admin site for low-level data access

## Technology stack

| Area            | Choice                                |
|-----------------|---------------------------------------|
| Language        | Python 3.8 – 3.12 (developed on 3.8)  |
| Framework       | Django 4.2 LTS                        |
| Config          | `django-environ` (`.env`)             |
| Forms           | `django-widget-tweaks`                |
| Static files    | WhiteNoise (compressed serving when `DEBUG=False`) |
| Images          | Pillow                               |
| Database        | SQLite by default; any `DATABASE_URL` |
| Frontend        | Server-rendered templates + one CSS file + progressive-enhancement JS |
| Tests           | Django test framework (32 tests)      |

> **Python version.** The project targets Django 4.2 LTS, which supports
> Python 3.8–3.12. The bundled virtualenv uses Python 3.8; any version in that
> range works. Pillow is pinned to 10.4.0 (the last series supporting 3.8).

## Architecture

```
insurancemanagement/     project config (settings, urls, wsgi/asgi)
customer/                 customer-facing app
  models.py               Customer
  forms.py                sign-up, profile, admin-edit forms
  views.py                dashboard, policies, applications, claims, renewals,
                          questions, recommendations
  urls.py                 /customer/* routes
insurance/                catalogue, admin area and shared domain logic
  models.py               Category, Policy, PolicyRecord, Question, Claim,
                          Notification
  forms.py                catalogue / review / calculator / recommendation forms
  views.py                public pages + all staff views
  permissions.py          is_customer / is_staff helpers + customer_required /
                          staff_required decorators
  services.py             calculate_premium(), recommend_policies() (pure,
                          testable, rule-based)
  utils.py                pagination helper
  context_processors.py   unread-notification badge
  templatetags/app_extras.py   querystring + badge helpers
  management/commands/seed_demo.py   demo data
templates/                project-level templates (base, dashboard shell,
                          partials, registration, insurance/, customer/)
static/css/app.css        design system
static/js/app.js          sidebar toggle, confirm modals, comparison picker
```

## Database relationships

```
User 1───1 Customer 1───* PolicyRecord *───1 Policy *───1 Category
                     │                    │
                     ├───* Question        └ (approved records carry
                     │                        start_date / end_date)
                     └───* Claim *───1 PolicyRecord

User 1───* Notification
```

* `Category` → `Policy` (`related_name="policies"`)
* `Policy` → `PolicyRecord` (`related_name="records"`)
* `Customer` → `PolicyRecord` (`related_name="policy_records"`),
  `Question` (`questions`), `Claim` (`claims`)
* `PolicyRecord` → `Claim` (`related_name="claims"`)
* `Notification` → `auth.User` (`related_name="notifications"`)
* All models carry `created_at` (`auto_now_add`) / `updated_at` (`auto_now`)
  timestamps. `PolicyRecord.status` and `Claim.status` are `TextChoices`
  (`Pending` / `Approved` / `Disapproved` or `Rejected`).
* Validation: phone regex on `Customer.mobile`; `MinValueValidator` on policy
  `sum_assurance` / `premium` / `tenure`; premium must be below sum assured;
  claim amount cannot exceed the policy's sum assured.

## Authentication / authorization

* Sessions + Django's auth backend.
* **Customer** = authenticated, `is_staff=False`, member of the `CUSTOMER`
  group, with a `Customer` row. Sign-up (`/customer/customersignup`) creates all
  three and enforces `AUTH_PASSWORD_VALIDATORS`.
* **Administrator** = authenticated with `is_staff=True` (create via
  `createsuperuser` or `seed_demo`).
* `customer_required` / `staff_required` decorators wrap every non-public view.
  Wrong-role access returns **403**; anonymous access redirects to the relevant
  login page.
* `/afterlogin` routes each user to the correct dashboard.
* Password change and reset use Django's built-in views.

## Security features

* Secrets and environment config never in source (`.env`, git-ignored); the app
  refuses to start with `DEBUG=False` and no `SECRET_KEY`.
* CSRF protection on every form; all destructive / state-changing actions
  (delete, approve, reject, renew, mark-read) are `POST`-only.
* Role separation enforced by decorators, not just template hiding — customers
  get `403` on staff URLs, staff get `403` on customer URLs.
* Object-level authorization: customer views fetch records scoped to
  `request.user` via `get_object_or_404`, so one customer cannot read or modify
  another's application, claim or renewal (no IDOR).
* Django password validators enforced on sign-up; admin editing a customer
  cannot touch the password hash.
* When `DEBUG=False`: `SECURE_SSL_REDIRECT`, HSTS (30 days, subdomains, preload),
  `Secure` + `HttpOnly` session/CSRF cookies, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`.
* `python manage.py check --deploy` passes (with a real 50-char key).

## Screenshots

Run the app and sign in with the demo accounts to see:

* `/` – public landing page
* `/premium-calculator` – calculator with breakdown
* `/customer/customer-dashboard` – customer dashboard
* `/customer/recommendations` – recommendation results with reasons
* `/admin-dashboard` – administrator overview

_(Add PNGs under `docs/` and link them here if you want them in the repo.)_

## Installation

```bash
git clone <repo-url>
cd insurance_management

# 1. Virtual environment
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Environment file (never committed)
cp .env.example .env                # Windows: copy .env.example .env

# 3. Generate a development secret key and paste it into .env as DJANGO_SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
#   .env already ships with DJANGO_DEBUG=True and safe local defaults.

# 4. Database + optional demo data
python manage.py migrate
python manage.py seed_demo          # optional: demo policies + accounts
python manage.py createsuperuser    # or use the seeded 'admin' account
```

If `python manage.py check` reports
`DJANGO_SECRET_KEY is required when DEBUG is False`, step 2/3 was skipped —
create `.env` and set a key.

## Environment variables

See `.env.example` for the annotated list. Key ones:

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Cryptographic key. **Required when `DEBUG=False`.** | insecure dev fallback only when `DEBUG=True` |
| `DJANGO_DEBUG` | Debug mode | `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames | `127.0.0.1,localhost` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins (with scheme) | empty |
| `DATABASE_URL` | Database connection URL | local SQLite |
| `EMAIL_BACKEND` | Email backend | console (prints to stdout) |
| `DEFAULT_FROM_EMAIL` / `CONTACT_RECEIVING_EMAILS` | Contact form addressing | — |

## How to run

```bash
python manage.py runserver
# http://127.0.0.1:8000/
```

Demo accounts (after `seed_demo`):

| Role     | Username   | Password        |
|----------|------------|-----------------|
| Admin    | `admin`    | `admin12345`    |
| Customer | `customer` | `customer12345` |

## How to run tests

```bash
python manage.py test
```

The 32 tests cover sign-up, login, role permissions, unauthorized access and
IDOR, policy creation, applications, approval/rejection, claims, the admin
customer-update password fix, renewals, the premium calculator, the
recommendation engine and the custom 403/404 error pages.

Other checks:

```bash
python manage.py check --deploy      # security review (run with DEBUG=False)
python manage.py collectstatic       # gather static files for deployment
```

## Limitations

* Renewal reminders and question/claim updates are **in-app notifications only** –
  no outbound email or scheduled job sends them yet.
* No payment/premium collection – applications and claims are tracked, not billed.
* Single SQLite database by default; no caching layer.
* `Claim` and `Notification` live in the `insurance` app for now rather than a
  dedicated app.
* The recommendation engine is deliberately rule-based, not machine learning.
* No file uploads for claims/KYC; profile picture is the only upload.

## Future improvements

* Payment / premium collection and receipts
* Document uploads for claims and KYC
* Email + scheduled task for renewal reminders (currently in-app only)
* Audit log of admin actions
* REST API (Django REST Framework) and a SPA frontend
* Move `Claim` / `Notification` into a dedicated app as the domain grows
* Replace the rule-based recommender with a trained model (and label it as ML
  only then)
* Dockerfile + CI pipeline
