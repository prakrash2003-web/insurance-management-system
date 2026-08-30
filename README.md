# Insurance Management System

A full-stack **Django 4.2** web application that models the day-to-day operations
of a small insurance provider. Customers can browse and compare policies, get a
transparent rule-based recommendation, estimate premiums, apply for cover, file
and track claims, and renew approved policies. Administrators manage the policy
catalogue and review every application, question and claim from a dedicated
dashboard.

> Built as a final-year / portfolio project with an emphasis on **role-based
> security**, **clean architecture**, **automated tests**, and a **modern
> responsive UI** — not just CRUD screens.

**Tech:** Python · Django 4.2 LTS · SQLite/PostgreSQL · WhiteNoise · server-rendered
templates · 32 automated tests · `manage.py check --deploy` clean.

---

## Problem statement

Small insurance providers often run their operations on spreadsheets, email and
paper forms. That approach has real problems:

* Customers have **no self-service** — they cannot see the policies on offer,
  compare them, check the status of an application, or file a claim without
  phoning an agent.
* Staff manually track applications, approvals, renewals and claims across
  disconnected tools, which is slow and error-prone.
* There is **no consistent way to recommend a suitable policy** to a customer, or
  to give them an up-front premium estimate.
* Ad-hoc systems rarely enforce **proper access control** — customer and staff
  capabilities leak into each other.

## Objectives

1. Provide a **single web application** for both customers and administrators.
2. Give customers genuine **self-service**: browse, compare, get recommendations,
   estimate premiums, apply, claim, renew, and ask questions.
3. Give administrators a **dashboard** to manage the catalogue and process
   applications, claims and questions with an audit trail of timestamps.
4. Enforce **strict role-based access control** and object-level authorization so
   a customer can never act as staff or touch another customer's data.
5. Offer a **transparent, explainable** policy recommendation and premium
   estimate — rules the user can actually read, not a black box.
6. Ship it like real software: environment-based config, no secrets in source,
   production security settings, and an automated test suite.

---

## Key features

| Area | Highlights |
|---|---|
| **Customers** | Dashboard, profile, browse/search/filter policies, policy comparison, premium calculator, rule-based recommendation, apply, application history & status, claims, renewals, Q&A, notifications, password reset |
| **Administrators** | Statistics dashboard, customer/category/policy CRUD, application review (approve/reject), claim review, question replies, search + filters + pagination everywhere |
| **Security** | Role separation (customer vs. staff), object-level authorization (no IDOR), CSRF everywhere, POST-only destructive actions, env-based secrets, production hardening |
| **Engineering** | `django-environ` config, pure/testable domain logic in `services.py`, custom decorators, 32 tests, custom 403/404/500 pages, WhiteNoise static serving |

### Customer features

* **Dashboard** – counts for available policies, applications (total / approved /
  pending), claims and questions, plus renewal alerts and recent activity.
* **Profile** – view and edit contact details and profile picture. Editing never
  exposes or changes the password.
* **Browse policies** – card grid with **search** (name/description) and
  **category filter**, paginated.
* **Policy detail** – full terms, premium rate, and an *Apply* action (disabled if
  an application is already active).
* **Policy comparison** – pick 2–4 policies and see them side-by-side
  (category, sum assured, premium, tenure, premium rate).
* **Premium calculator** – see below.
* **Rule-based policy recommendation** – see below.
* **Apply for a policy** – one active application per policy; duplicate
  submissions are blocked.
* **Application history** – filter by status, open any application for full
  detail including cover period and renewal status.
* **Claims** – file a claim against an approved policy, track its status, read
  administrator remarks.
* **Renewals** – approved policies get a cover period; renew when due or expired.
* **Questions** – ask a question and read the administrator's reply.
* **Notifications** – in-app feed + unread badge for application decisions, claim
  updates, question replies and renewals.
* **Account** – change password, and a full password-reset-by-email flow.

### Administrator features

* **Statistics dashboard** – customers, policies, categories, applications by
  status, claims (total / pending), unanswered questions, total sum assured, with
  recent-applications and recent-claims tables.
* **Customer management** – search by name / username / email / mobile; edit the
  login account (name, email, active flag — **no password field**) and contact
  details; delete with a confirmation step.
* **Category management** – create / edit / delete, with a policy count per
  category and search.
* **Policy management** – create / edit / delete, search, filter by category,
  applicant count, active/inactive toggle; the form validates that premium is
  below the sum assured.
* **Application review** – list with status filter and search; **approve** (sets
  the cover start/end dates and notifies the customer) or **reject** (notifies
  the customer). Both are POST-only.
* **Claim review** – list with status filter; open a claim, set its status and
  add remarks; the customer is notified.
* **Questions** – filter answered / unanswered; reply, which marks the question
  answered and notifies the customer.
* **Django admin** – the built-in admin is configured (`list_display`,
  `list_filter`, `search_fields`, `date_hierarchy`) for low-level data access.

### Rule-Based Policy Recommendation

**This is a transparent, rule-based system — it is not machine learning.**
There is no trained model, no dataset and no statistical inference. Every score
is produced by explicit, readable rules in `insurance/services.py`
(`recommend_policies`), and the UI shows the reasons behind each result.

The customer provides: **age**, **annual income**, **number of dependents**,
**desired coverage** and (optionally) an **insurance category**. Each active
policy is then scored out of 100:

| Rule | Max points | Logic |
|---|---|---|
| Coverage match | 35 | Sum assured within 0.8–1.5× of the requested coverage scores full; partial credit for near misses |
| Premium affordability | 30 | Annual premium at or below ~15% of annual income; more headroom scores higher |
| Tenure suitability | 20 | Longer tenure for younger applicants, shorter for older applicants |
| Dependents | 10 | Adequate cover for 2+ dependents |
| Category match | 5 | Policy category matches the requested one |

Policies are returned best-first with a match label (*Excellent / Good / Partial*)
and a bullet list such as:

> **Recommended because:**
> * Coverage of 1,000,000 closely matches your requested 1,000,000
> * Annual premium 8,000 fits within ~15% of your income (15,000)
> * Long tenure suits your age group

### Premium Calculator

A public, explainable estimator (`insurance/services.py`, `calculate_premium`).
Inputs: age, desired sum assured, tenure, category, smoker status. It returns an
estimated **annual** and **monthly** premium, the **total over the tenure**, and
a full breakdown table of every factor applied:

```
Base premium      1,000,000 × 0.02 base rate      20,000.00
Age factor        age 30                          × 1.00
Tenure factor     20 year(s)                      × 0.9000
Smoker factor     non-smoker                      × 1.00
Category factor   Life                            × 1.00
```

The listed premium of a real policy is still whatever the provider sets; this is
guidance only.

### Claims

`Claim` links a customer to one of their **approved** `PolicyRecord`s and carries
the claim amount, description, status (`Pending` / `Approved` / `Rejected`),
administrator remarks and created/updated timestamps. The form rejects a claim
amount greater than the policy's sum assured. Customers file and track claims;
administrators review them and the customer is notified of the decision.

### Renewals & expiry

When an application is approved, the `PolicyRecord` gets a `start_date` and an
`end_date` (`start + tenure years`). A computed `renewal_status`
(`Active` / `Due` / `Expired`) drives dashboard alerts and the renewals page,
where a customer can extend an approved policy for another full tenure.

### Notifications

`Notification` is a lightweight per-user feed (`message`, optional link, kind,
read flag, timestamp). `Notification.notify(user, message, url, kind)` is called
on: application submitted / approved / rejected, claim submitted / status
changed, question answered, and renewal. A context processor exposes the unread
count to every page for the topbar badge.

---

## Security features

* **No secrets in source.** `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`,
  `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` and email settings come from the
  environment (`.env`, git-ignored). The app **refuses to start** with
  `DEBUG=False` and no `SECRET_KEY`.
* **Role separation is enforced in code**, not just by hiding links.
  `customer_required` / `staff_required` decorators wrap every non-public view —
  a customer hitting a staff URL gets **403**, staff hitting a customer URL gets
  **403**, anonymous users are redirected to the correct login.
* **Object-level authorization (no IDOR).** Customer views fetch records scoped to
  `request.user` via `get_object_or_404`, so customer A cannot read or modify
  customer B's application, claim or renewal (covered by tests).
* **CSRF protection on every form**; every destructive / state-changing action
  (delete, approve, reject, renew, mark-read, apply) is **POST-only**.
* **Password safety.** Django's password validators are enforced on sign-up; an
  administrator editing a customer cannot touch the password hash.
* **Production hardening (auto-on when `DEBUG=False`):** `SECURE_SSL_REDIRECT`,
  HSTS (30 days, subdomains, preload), `Secure` + `HttpOnly` session/CSRF
  cookies, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: same-origin`.
* `python manage.py check --deploy` reports **0 issues** (with a real key).

---

## Project highlights

The parts most worth looking at in a review:

* **`insurance/permissions.py`** – tiny, explicit RBAC layer: `is_customer` /
  `is_staff_user` predicates and `customer_required` / `staff_required`
  decorators that compose `login_required` + a role check and raise
  `PermissionDenied` (→ custom 403 page) on mismatch.
* **`insurance/services.py`** – all domain logic (`calculate_premium`,
  `recommend_policies`) is **pure Python with no Django/database dependency**, so
  it is trivial to unit-test and reason about. The recommendation rules are data
  (`AGE_FACTORS`, `CATEGORY_FACTORS`) + a documented scoring function.
* **Object-level auth pattern** – every customer detail view is
  `get_object_or_404(Model, pk=pk, customer=request.user.customer)`, which turns
  an authorization bug into a clean 404. Backed by explicit IDOR tests.
* **`PolicyRecord` as a lifecycle model** – `TextChoices` status, `approve()` /
  `disapprove()` methods that also manage cover dates, and computed properties
  (`days_to_expiry`, `is_expired`, `needs_renewal`, `renewal_status`).
* **Environment config** – `django-environ` with safe defaults; a blank
  `DATABASE_URL` falls back to SQLite instead of crashing; the missing-key error
  message tells you exactly what to do.
* **Design system in one file** – `static/css/app.css` (CSS custom properties,
  ~1 accent colour, no framework, no CDN) + `static/js/app.js` for progressive
  enhancement (mobile nav, confirmation modals, comparison picker). Custom
  `400/403/404/500` pages match it.
* **Tests as documentation** – `insurance/tests.py` / `customer/tests.py` read as
  a spec of the security and business rules (32 tests).

---

## Technology stack

| Area | Choice |
|---|---|
| Language | Python 3.8 – 3.12 (developed on 3.8) |
| Framework | Django 4.2 LTS |
| Configuration | `django-environ` (`.env`) |
| Forms | `django-widget-tweaks` |
| Static files | WhiteNoise (compressed serving, works without a web server) |
| Images | Pillow |
| Database | SQLite by default; PostgreSQL in production via `DATABASE_URL` (`psycopg2`) |
| Prod server | Gunicorn |
| Hosting | Railway (`railway.json`, `.python-version`) |
| Frontend | Server-rendered Django templates + one hand-written CSS file + vanilla JS |
| Tests | Django test framework (32 tests) |

> **Python version.** Django 4.2 LTS supports Python 3.8–3.12; any version in
> that range works. The bundled virtualenv uses 3.8, so Pillow is pinned to
> 10.4.0 (the last series supporting 3.8). Railway builds on **Python 3.12**
> (`.python-version`, via the Nixpacks builder). `psycopg2-binary` is skipped on
> Windows (SQLite locally).

---

## Architecture

Two Django apps plus the project package:

```
insurancemanagement/          project config
  settings.py                 env-driven; security auto-hardens when DEBUG=False
  urls.py                     root routes + auth + favicon + media (DEBUG)

customer/                     customer-facing app
  models.py                   Customer (1-1 with auth.User)
  forms.py                    sign-up, profile, admin-edit forms (password-safe)
  views.py                    dashboard, policies, comparison, apply, history,
                              claims, renewals, questions, recommendations
  urls.py                     /customer/* routes

insurance/                    catalogue, staff area, shared domain logic
  models.py                   Category, Policy, PolicyRecord, Question,
                              Claim, Notification
  forms.py                    catalogue / review / calculator / recommendation
  views.py                    public pages + every staff view
  permissions.py              role predicates + customer_required/staff_required
  services.py                 calculate_premium(), recommend_policies() — pure
  utils.py                    pagination helper
  context_processors.py       unread-notification badge
  templatetags/app_extras.py  querystring + status-badge helpers
  admin.py                    configured Django admin for all models
  management/commands/seed_demo.py   demo data + demo accounts

templates/                    project-level templates
  base.html                   public shell (navbar + footer)
  dashboard_base.html         authenticated shell (sidebar + topbar)
  400/403/404/500.html        custom error pages
  partials/                   _form, _pagination, _messages, _confirm_modal
  registration/               login + password change/reset
  customer/  insurance/       per-feature pages

static/css/app.css            design system
static/js/app.js              progressive enhancement
static/favicon.svg            app icon
```

Request flow: `URLconf → decorator (auth + role) → view → service (pure logic) →
model → template`. All list views share `paginate()` and the search/filter
pattern; all templates extend one of two base shells.

## Database relationships

```
auth.User 1───1 Customer 1───* PolicyRecord *───1 Policy *───1 Category
                        │                    │
                        ├───* Question        └ approved records carry
                        │                       start_date / end_date
                        └───* Claim *───1 PolicyRecord

auth.User 1───* Notification
```

| From | To | `related_name` |
|---|---|---|
| `Category` | `Policy` | `policies` |
| `Policy` | `PolicyRecord` | `records` |
| `Customer` | `PolicyRecord` | `policy_records` |
| `Customer` | `Question` | `questions` |
| `Customer` | `Claim` | `claims` |
| `PolicyRecord` | `Claim` | `claims` |
| `auth.User` | `Notification` | `notifications` |

* Every model has `created_at` (`auto_now_add`) and `updated_at` (`auto_now`).
* `PolicyRecord.status` and `Claim.status` are `TextChoices`.
* Validation: phone regex on `Customer.mobile`; `MinValueValidator` on policy
  `sum_assurance` / `premium` / `tenure`; form-level "premium < sum assured" and
  "claim amount ≤ sum assured".

## Authentication / authorization

* Session auth on top of `django.contrib.auth`.
* **Customer** = authenticated, `is_staff=False`, in the `CUSTOMER` group, with a
  `Customer` row. Sign-up creates all three atomically and enforces
  `AUTH_PASSWORD_VALIDATORS`.
* **Administrator** = authenticated with `is_staff=True` (`createsuperuser` or
  `seed_demo`).
* `/afterlogin` routes each user to the right dashboard.
* Password change and reset use Django's built-in views with custom templates.

---

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

# 3. Generate a secret key and paste it into .env as DJANGO_SECRET_KEY=
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
#    .env already sets DJANGO_DEBUG=True and safe local defaults.

# 4. Database + optional demo data
python manage.py migrate
python manage.py seed_demo          # optional: demo policies + demo accounts
python manage.py createsuperuser    # or just use the seeded 'admin' account
```

If `python manage.py check` says
`DJANGO_SECRET_KEY is required when DEBUG is False`, step 2/3 was skipped.

## Environment setup

Everything is read from `.env` (see `.env.example` for the annotated list):

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Cryptographic key. **Required when `DEBUG=False`.** | insecure dev fallback only when `DEBUG=True` |
| `DJANGO_DEBUG` | Debug mode | `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames | `127.0.0.1,localhost` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins (with scheme) | empty |
| `DATABASE_URL` | DB connection URL (`postgres://…`); blank ⇒ local SQLite | SQLite |
| `DJANGO_DB_CONN_MAX_AGE` | Persistent DB connection lifetime, seconds | `0` |
| `EMAIL_BACKEND` | Email backend | console (prints to stdout) |
| `DEFAULT_FROM_EMAIL` / `CONTACT_RECEIVING_EMAILS` | Contact form / reset addressing | — |
| `DJANGO_SECURE_SSL_REDIRECT` | Force HTTPS (production only) | `True` when `DEBUG=False` |
| `RAILWAY_PUBLIC_DOMAIN` | Injected by Railway; auto-trusted for hosts + CSRF | — |

## Running locally

```bash
python manage.py runserver
# open http://127.0.0.1:8000/
```

## Running tests

```bash
python manage.py test                       # 32 tests
python manage.py check                       # system check
python manage.py check --deploy              # security review (set DJANGO_DEBUG=False)
python manage.py makemigrations --check --dry-run
```

The tests cover: sign-up (and weak-password rejection), login, role permissions,
anonymous redirects, **IDOR** (cross-customer access → 404), policy creation and
validation, applications (POST-only, dedup, notification), approve/reject
(dates + notification, customer blocked), claims (filing, amount cap, admin
review, cross-customer 404), the admin customer-update password fix, renewal
status transitions and renewal, the premium calculator, the recommendation
engine (scoring + reasons + ordering), and the custom 403/404 pages.

## Demo / admin setup

`python manage.py seed_demo` creates four categories, six policies, and:

| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `admin12345` |
| Customer | `customer` | `customer12345` |

These credentials are **for local demos only**. In any real deployment, create
accounts with `createsuperuser` / sign-up and do not run `seed_demo`.

## Deployment (Railway)

The project is ready to deploy on [Railway](https://railway.app) with a managed
PostgreSQL database. Nothing about the local SQLite workflow changes.

**What's in the repo for deployment**

| File | Purpose |
|---|---|
| `requirements.txt` | adds `gunicorn` (WSGI server) and `psycopg2-binary` (Postgres driver, Linux only) |
| `.python-version` | Python `3.12` for the build |
| `railway.json` | builder (**Nixpacks**), build command, start command (migrate + Gunicorn), restart policy |
| `settings.py` | already env-driven; auto-trusts `RAILWAY_PUBLIC_DOMAIN`; WhiteNoise for static |

> **Builder note.** `railway.json` sets `"builder": "NIXPACKS"`. Railway's newer
> default builder (Railpack) provisions Python with `mise`, which rejects older
> CPython artifacts that lack GitHub attestations (e.g. 3.12.7). Nixpacks uses
> Nix packages instead and is unaffected.

**Steps**

1. **Create the project.** Railway → *New Project* → *Deploy from GitHub repo* →
   pick `insurance-management-system`.
2. **Add PostgreSQL.** In the project, *New* → *Database* → *Add PostgreSQL*.
   Railway creates a `DATABASE_URL` variable; reference it on the web service:
   in the web service → *Variables* → *New Variable* →
   `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (Railway's reference syntax).
3. **Set the web service variables** (service → *Variables*):

   | Variable | Value |
   |---|---|
   | `DJANGO_SECRET_KEY` | a fresh 50-char key — `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"` |
   | `DJANGO_DEBUG` | `False` |
   | `DJANGO_ALLOWED_HOSTS` | `${{RAILWAY_PUBLIC_DOMAIN}}` (or your custom domain) |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://${{RAILWAY_PUBLIC_DOMAIN}}` |
   | `DJANGO_DB_CONN_MAX_AGE` | `600` |
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |

   `DEFAULT_FROM_EMAIL` / `EMAIL_*` are optional (email defaults to the console
   backend). Do **not** set `PORT` — Railway provides it.
4. **Generate the public domain.** Web service → *Settings* → *Networking* →
   *Generate Domain*. Railway now sets `RAILWAY_PUBLIC_DOMAIN`, which the app
   trusts automatically. Redeploy if the first deploy happened before this.
5. **Build & release run automatically (from `railway.json`):**
   * Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`.
   * Start: `python manage.py migrate --noinput` then Gunicorn on `$PORT`.
6. **Create an admin user** — one-off, from your machine with the Railway CLI:

   ```bash
   npm i -g @railway/cli      # once
   railway link               # select the project
   railway run python manage.py createsuperuser
   ```

   (or open the service's *Shell* in the Railway dashboard and run the same command.)

**Commands reference**

| Purpose | Command |
|---|---|
| Build | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
| Start | `python manage.py migrate --noinput && gunicorn insurancemanagement.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --access-logfile - --error-logfile -` |
| Migrate (manual) | `railway run python manage.py migrate` |
| Collectstatic (manual) | `railway run python manage.py collectstatic --noinput` |
| Superuser | `railway run python manage.py createsuperuser` |

**Notes**

* Uploaded profile pictures are written to the container filesystem, which is
  **ephemeral** — they are lost on redeploy. For persistence, add a Railway
  **Volume** mounted at `/app/media`, or switch `MEDIA_ROOT` to object storage.
  The feature degrades gracefully (a missing picture just shows initials).
* `DEBUG` stays `False`; HTTPS redirect, HSTS and `Secure` cookies switch on
  automatically. Railway terminates TLS and forwards `X-Forwarded-Proto`, which
  `SECURE_PROXY_SSL_HEADER` already handles.

## Screenshots

Run the app and sign in with the demo accounts:

| Page | Path |
|---|---|
| Public landing | `/` |
| Premium calculator | `/premium-calculator` |
| Customer dashboard | `/customer/customer-dashboard` |
| Policy recommendation (with reasons) | `/customer/recommendations` |
| Administrator dashboard | `/admin-dashboard` |

_Add PNGs under `docs/` and link them here for the portfolio version._

---

## Limitations

* Renewal reminders and question/claim updates are **in-app notifications only** —
  no outbound email or scheduled job sends them.
* No payment / premium collection — applications and claims are tracked, not billed.
* Single SQLite database by default; no caching layer.
* `Claim` and `Notification` live in the `insurance` app rather than their own.
* The recommendation engine is deliberately rule-based, not machine learning.
* Profile picture is the only file upload; no claim/KYC document uploads.
* On Railway the container filesystem is ephemeral, so uploaded profile pictures
  do not survive a redeploy unless a Volume is mounted at the media directory
  (see *Deployment*). The app handles a missing picture gracefully.

## Future improvements

* Payment / premium collection and receipts
* Document uploads for claims and KYC
* Email + a scheduled task for renewal reminders
* Audit log of administrator actions
* REST API (Django REST Framework) + SPA frontend
* Move `Claim` / `Notification` into a dedicated app as the domain grows
* Replace the rule-based recommender with a trained model (and rename it only then)
* Dockerfile + CI pipeline
