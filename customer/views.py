from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from insurance import forms as iforms
from insurance import models as imodels
from insurance.permissions import CUSTOMER_GROUP, customer_required
from insurance.services import recommend_policies
from insurance.utils import paginate

from . import forms, models


def _customer(request):
    return get_object_or_404(models.Customer, user=request.user)


# ---------------------------------------------------------------------------
# Public / auth
# ---------------------------------------------------------------------------
def customerclick_view(request):
    if request.user.is_authenticated:
        return redirect("afterlogin")
    return render(request, "customer/customerclick.html")


def customer_signup_view(request):
    if request.user.is_authenticated:
        return redirect("afterlogin")
    user_form = forms.CustomerUserForm()
    profile_form = forms.CustomerProfileForm()
    if request.method == "POST":
        user_form = forms.CustomerUserForm(request.POST)
        profile_form = forms.CustomerProfileForm(request.POST, request.FILES)
        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic():
                user = user_form.save(commit=False)
                user.set_password(user_form.cleaned_data["password"])
                user.save()
                customer = profile_form.save(commit=False)
                customer.user = user
                customer.save()
                group, _ = Group.objects.get_or_create(name=CUSTOMER_GROUP)
                user.groups.add(group)
            messages.success(request, "Account created. Please log in.")
            return redirect("customerlogin")
        messages.error(request, "Please correct the errors below.")
    return render(
        request,
        "customer/customersignup.html",
        {"userForm": user_form, "customerForm": profile_form},
    )


# ---------------------------------------------------------------------------
# Dashboard / profile
# ---------------------------------------------------------------------------
@customer_required
def customer_dashboard_view(request):
    customer = _customer(request)
    records = customer.policy_records.select_related("policy")
    context = {
        "customer": customer,
        "available_policy": imodels.Policy.objects.filter(is_active=True).count(),
        "applied_policy": records.count(),
        "approved_policy": records.filter(status=imodels.PolicyRecord.Status.APPROVED).count(),
        "pending_policy": records.filter(status=imodels.PolicyRecord.Status.PENDING).count(),
        "total_category": imodels.Category.objects.count(),
        "total_question": customer.questions.count(),
        "total_claims": customer.claims.count(),
        "recent_records": records[:5],
        "renewals_due": [r for r in records if r.renewal_status in {
            imodels.PolicyRecord.RenewalStatus.DUE,
            imodels.PolicyRecord.RenewalStatus.EXPIRED,
        }],
    }
    return render(request, "customer/customer_dashboard.html", context)


@customer_required
def customer_profile_view(request):
    return render(request, "customer/profile.html", {"customer": _customer(request)})


@customer_required
def customer_profile_edit_view(request):
    customer = _customer(request)
    user_form = forms.CustomerUserUpdateForm(instance=request.user)
    profile_form = forms.CustomerProfileForm(instance=customer)
    if request.method == "POST":
        user_form = forms.CustomerUserUpdateForm(request.POST, instance=request.user)
        profile_form = forms.CustomerProfileForm(request.POST, request.FILES, instance=customer)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated.")
            return redirect("customer-profile")
    return render(
        request,
        "customer/profile_edit.html",
        {"userForm": user_form, "customerForm": profile_form},
    )


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
@customer_required
def policy_list_view(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    policies = imodels.Policy.objects.filter(is_active=True).select_related("category")
    if q:
        policies = policies.filter(
            Q(policy_name__icontains=q) | Q(description__icontains=q)
        )
    if category:
        policies = policies.filter(category_id=category)
    return render(
        request,
        "customer/policy_list.html",
        {
            "page_obj": paginate(request, policies, per_page=9),
            "q": q,
            "categories": imodels.Category.objects.all(),
            "selected_category": category,
        },
    )


@customer_required
def policy_detail_view(request, pk):
    policy = get_object_or_404(
        imodels.Policy.objects.select_related("category"), pk=pk, is_active=True
    )
    customer = _customer(request)
    existing = customer.policy_records.filter(policy=policy).order_by("-created_at").first()
    return render(
        request,
        "customer/policy_detail.html",
        {"policy": policy, "existing": existing},
    )


@customer_required
def policy_compare_view(request):
    ids = [i for i in request.GET.get("ids", "").split(",") if i.strip().isdigit()][:4]
    policies = imodels.Policy.objects.filter(
        id__in=ids, is_active=True
    ).select_related("category")
    return render(
        request,
        "customer/policy_compare.html",
        {
            "policies": policies,
            "all_policies": imodels.Policy.objects.filter(is_active=True),
        },
    )


@require_POST
@customer_required
def apply_view(request, pk):
    policy = get_object_or_404(imodels.Policy, pk=pk, is_active=True)
    customer = _customer(request)
    active = customer.policy_records.filter(
        policy=policy,
        status__in=[
            imodels.PolicyRecord.Status.PENDING,
            imodels.PolicyRecord.Status.APPROVED,
        ],
    ).exists()
    if active:
        messages.info(request, "You already have an active application for this policy.")
        return redirect("history")
    imodels.PolicyRecord.objects.create(customer=customer, policy=policy)
    imodels.Notification.notify(
        request.user,
        f"Application submitted for '{policy.policy_name}'.",
        url="/customer/history",
    )
    messages.success(request, "Application submitted.")
    return redirect("history")


@customer_required
def application_history_view(request):
    customer = _customer(request)
    records = customer.policy_records.select_related("policy__category")
    status = request.GET.get("status", "").strip()
    if status:
        records = records.filter(status=status)
    return render(
        request,
        "customer/history.html",
        {
            "page_obj": paginate(request, records),
            "statuses": imodels.PolicyRecord.Status.choices,
            "selected_status": status,
        },
    )


@customer_required
def application_detail_view(request, pk):
    record = get_object_or_404(
        imodels.PolicyRecord.objects.select_related("policy__category"),
        pk=pk,
        customer=_customer(request),
    )
    return render(request, "customer/application_detail.html", {"record": record})


# ---------------------------------------------------------------------------
# Renewals
# ---------------------------------------------------------------------------
@customer_required
def renewal_view(request):
    customer = _customer(request)
    records = [
        r
        for r in customer.policy_records.select_related("policy")
        if r.renewal_status
        in {
            imodels.PolicyRecord.RenewalStatus.DUE,
            imodels.PolicyRecord.RenewalStatus.EXPIRED,
            imodels.PolicyRecord.RenewalStatus.ACTIVE,
        }
    ]
    return render(request, "customer/renewals.html", {"records": records})


@require_POST
@customer_required
def renew_view(request, pk):
    record = get_object_or_404(
        imodels.PolicyRecord, pk=pk, customer=_customer(request),
        status=imodels.PolicyRecord.Status.APPROVED,
    )
    base = max(record.end_date or timezone.now().date(), timezone.now().date())
    record.end_date = base + timedelta(days=365 * record.policy.tenure)
    record.renewal_reminder_sent = False
    record.save(update_fields=["end_date", "renewal_reminder_sent", "updated_at"])
    imodels.Notification.notify(
        request.user,
        f"'{record.policy.policy_name}' renewed until {record.end_date}.",
        url="/customer/renewals",
        kind=imodels.Notification.Kind.SUCCESS,
    )
    messages.success(request, "Policy renewed.")
    return redirect("renewals")


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
@customer_required
def ask_question_view(request):
    customer = _customer(request)
    form = iforms.QuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.customer = customer
        question.save()
        messages.success(request, "Question submitted.")
        return redirect("question-history")
    return render(request, "customer/ask_question.html", {"questionForm": form})


@customer_required
def question_history_view(request):
    customer = _customer(request)
    return render(
        request,
        "customer/question_history.html",
        {"page_obj": paginate(request, customer.questions.all())},
    )


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------
@customer_required
def claim_list_view(request):
    customer = _customer(request)
    claims = customer.claims.select_related("policy_record__policy")
    return render(
        request,
        "customer/claim_list.html",
        {"page_obj": paginate(request, claims)},
    )


@customer_required
def claim_create_view(request):
    customer = _customer(request)
    form = iforms.ClaimForm(request.POST or None, customer=customer)
    if request.method == "POST" and form.is_valid():
        claim = form.save(commit=False)
        claim.customer = customer
        claim.save()
        imodels.Notification.notify(
            request.user,
            f"Claim #{claim.pk} submitted and under review.",
            url="/customer/claims",
        )
        messages.success(request, "Claim submitted.")
        return redirect("claim-list")
    return render(request, "customer/claim_form.html", {"form": form})


@customer_required
def claim_detail_view(request, pk):
    claim = get_object_or_404(
        imodels.Claim.objects.select_related("policy_record__policy"),
        pk=pk,
        customer=_customer(request),
    )
    return render(request, "customer/claim_detail.html", {"claim": claim})


# ---------------------------------------------------------------------------
# Recommendation (rule-based)
# ---------------------------------------------------------------------------
@customer_required
def recommendation_view(request):
    form = iforms.RecommendationForm(request.GET or None)
    recommendations = None
    if request.GET and form.is_valid():
        category = form.cleaned_data["category"]
        policies = imodels.Policy.objects.filter(is_active=True).select_related("category")
        if category:
            policies = policies.filter(category=category)
        recommendations = recommend_policies(
            policies,
            age=form.cleaned_data["age"],
            annual_income=form.cleaned_data["annual_income"],
            dependents=form.cleaned_data["dependents"],
            desired_coverage=form.cleaned_data["desired_coverage"],
            category_name=category.category_name if category else None,
        )
    return render(
        request,
        "customer/recommendations.html",
        {"form": form, "recommendations": recommendations},
    )
