from django.conf import settings
from django.contrib import messages
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.mail import BadHeaderError, send_mail
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from customer.forms import CustomerProfileForm
from customer.models import Customer

from . import forms, models
from .permissions import is_customer, staff_required
from .services import calculate_premium
from .utils import paginate


# ---------------------------------------------------------------------------
# Public site
# ---------------------------------------------------------------------------
def home_view(request):
    # Only bounce users who actually have a dashboard. A logged-in account with
    # no role stays on the public home page (redirecting it to /afterlogin - which
    # would redirect back here - was an infinite loop).
    if request.user.is_authenticated and (
        request.user.is_staff or is_customer(request.user)
    ):
        return redirect("afterlogin")
    return render(request, "insurance/index.html")


def aboutus_view(request):
    return render(request, "insurance/aboutus.html")


def contactus_view(request):
    form = forms.ContactusForm()
    if request.method == "POST":
        form = forms.ContactusForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            email = form.cleaned_data["email"]
            message = form.cleaned_data["message"]
            recipients = settings.CONTACT_RECEIVING_EMAILS
            if not recipients:
                messages.warning(
                    request, "Contact form is not configured. Please try later."
                )
            else:
                try:
                    send_mail(
                        subject=f"[Contact] message from {name}",
                        message=f"From: {name} <{email}>\n\n{message}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=recipients,
                        fail_silently=False,
                    )
                    return render(request, "insurance/contactussuccess.html")
                except BadHeaderError:
                    messages.error(request, "Invalid header found.")
    return render(request, "insurance/contactus.html", {"form": form})


@login_required
def afterlogin_view(request):
    if request.user.is_staff:
        return redirect("admin-dashboard")
    if is_customer(request.user):
        return redirect("customer-dashboard")
    messages.error(request, "Your account has no role assigned. Contact an administrator.")
    return redirect("home")


class AdminLoginView(LoginView):
    template_name = "registration/admin_login.html"
    # Same form Django's own /admin/ uses: standard authenticate() +
    # ModelBackend, plus an is_staff requirement. A non-staff account is
    # rejected here (it should use the customer login).
    authentication_form = AdminAuthenticationForm
    redirect_authenticated_user = True


def premium_calculator_view(request):
    form = forms.PremiumCalculatorForm(request.GET or None)
    result = None
    if request.GET and form.is_valid():
        category = form.cleaned_data["category"]
        result = calculate_premium(
            age=form.cleaned_data["age"],
            sum_assured=form.cleaned_data["sum_assured"],
            tenure=form.cleaned_data["tenure"],
            category_name=category.category_name if category else None,
            smoker=form.cleaned_data["smoker"],
        )
    return render(
        request,
        "insurance/premium_calculator.html",
        {"form": form, "result": result},
    )


# ---------------------------------------------------------------------------
# Notifications (any authenticated user)
# ---------------------------------------------------------------------------
@login_required
def notifications_view(request):
    page = paginate(request, request.user.notifications.all(), per_page=20)
    return render(request, "insurance/notifications.html", {"page_obj": page})


@require_POST
@login_required
def notification_read_view(request, pk):
    note = get_object_or_404(models.Notification, pk=pk, user=request.user)
    note.is_read = True
    note.save(update_fields=["is_read"])
    return redirect(request.POST.get("next") or note.url or "notifications")


@require_POST
@login_required
def notification_read_all_view(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect(request.POST.get("next") or "notifications")


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------
@staff_required
def admin_dashboard_view(request):
    records = models.PolicyRecord.objects.all()
    context = {
        "total_user": Customer.objects.count(),
        "total_policy": models.Policy.objects.count(),
        "total_category": models.Category.objects.count(),
        "total_question": models.Question.objects.count(),
        "unanswered_question": models.Question.objects.filter(is_answered=False).count(),
        "total_policy_holder": records.count(),
        "approved_policy_holder": records.filter(status=models.PolicyRecord.Status.APPROVED).count(),
        "disapproved_policy_holder": records.filter(status=models.PolicyRecord.Status.DISAPPROVED).count(),
        "waiting_policy_holder": records.filter(status=models.PolicyRecord.Status.PENDING).count(),
        "total_claims": models.Claim.objects.count(),
        "pending_claims": models.Claim.objects.filter(status=models.Claim.Status.PENDING).count(),
        "assured_sum": models.Policy.objects.aggregate(t=Sum("sum_assurance"))["t"] or 0,
        "recent_records": records.select_related("customer__user", "policy")[:8],
        "recent_claims": models.Claim.objects.select_related("policy_record__policy", "customer__user")[:8],
    }
    return render(request, "insurance/admin_dashboard.html", context)


# ---------------------------------------------------------------------------
# Admin: customers
# ---------------------------------------------------------------------------
@staff_required
def admin_view_customer_view(request):
    q = request.GET.get("q", "").strip()
    customers = (
        Customer.objects.select_related("user")
        .annotate(record_count=Count("policy_records"))
        .order_by("user__first_name", "user__last_name")
    )
    if q:
        customers = customers.filter(
            Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__email__icontains=q)
            | Q(mobile__icontains=q)
        )
    return render(
        request,
        "insurance/admin_view_customer.html",
        {"page_obj": paginate(request, customers), "q": q},
    )


@staff_required
def update_customer_view(request, pk):
    customer = get_object_or_404(Customer.objects.select_related("user"), pk=pk)
    user_form = forms.AdminCustomerUpdateForm(instance=customer.user)
    profile_form = CustomerProfileForm(instance=customer)
    if request.method == "POST":
        user_form = forms.AdminCustomerUpdateForm(request.POST, instance=customer.user)
        profile_form = CustomerProfileForm(request.POST, request.FILES, instance=customer)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Customer updated.")
            return redirect("admin-view-customer")
    return render(
        request,
        "insurance/update_customer.html",
        {"userForm": user_form, "customerForm": profile_form, "customer": customer},
    )


@staff_required
def delete_customer_view(request, pk):
    customer = get_object_or_404(Customer.objects.select_related("user"), pk=pk)
    if request.method == "POST":
        customer.user.delete()  # cascades to Customer + related records
        messages.success(request, "Customer account deleted.")
        return redirect("admin-view-customer")
    return render(
        request,
        "insurance/confirm_delete.html",
        {"object": customer, "title": "Delete customer", "cancel_url": "admin-view-customer"},
    )


# ---------------------------------------------------------------------------
# Admin: categories
# ---------------------------------------------------------------------------
@staff_required
def admin_category_view(request):
    return redirect("admin-view-category")


@staff_required
def admin_view_category_view(request):
    q = request.GET.get("q", "").strip()
    categories = models.Category.objects.annotate(
        policy_count=Count("policies")
    ).order_by("category_name")
    if q:
        categories = categories.filter(category_name__icontains=q)
    return render(
        request,
        "insurance/admin_view_category.html",
        {"page_obj": paginate(request, categories), "q": q},
    )


@staff_required
def admin_add_category_view(request):
    form = forms.CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category created.")
        return redirect("admin-view-category")
    return render(request, "insurance/category_form.html", {"categoryForm": form, "mode": "Add"})


@staff_required
def update_category_view(request, pk):
    category = get_object_or_404(models.Category, pk=pk)
    form = forms.CategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category updated.")
        return redirect("admin-view-category")
    return render(request, "insurance/category_form.html", {"categoryForm": form, "mode": "Update"})


@staff_required
def delete_category_view(request, pk):
    category = get_object_or_404(models.Category, pk=pk)
    if request.method == "POST":
        category.delete()
        messages.success(request, "Category deleted.")
        return redirect("admin-view-category")
    return render(
        request,
        "insurance/confirm_delete.html",
        {"object": category, "title": "Delete category", "cancel_url": "admin-view-category"},
    )


# ---------------------------------------------------------------------------
# Admin: policies
# ---------------------------------------------------------------------------
@staff_required
def admin_policy_view(request):
    return redirect("admin-view-policy")


@staff_required
def admin_view_policy_view(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    policies = (
        models.Policy.objects.select_related("category")
        .annotate(applicant_count=Count("records"))
        .order_by("policy_name")
    )
    if q:
        policies = policies.filter(policy_name__icontains=q)
    if category:
        policies = policies.filter(category_id=category)
    return render(
        request,
        "insurance/admin_view_policy.html",
        {
            "page_obj": paginate(request, policies),
            "q": q,
            "categories": models.Category.objects.all(),
            "selected_category": category,
        },
    )


@staff_required
def admin_add_policy_view(request):
    form = forms.PolicyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Policy created.")
        return redirect("admin-view-policy")
    return render(request, "insurance/policy_form.html", {"policyForm": form, "mode": "Add"})


@staff_required
def update_policy_view(request, pk):
    policy = get_object_or_404(models.Policy, pk=pk)
    form = forms.PolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Policy updated.")
        return redirect("admin-view-policy")
    return render(request, "insurance/policy_form.html", {"policyForm": form, "mode": "Update"})


@staff_required
def delete_policy_view(request, pk):
    policy = get_object_or_404(models.Policy, pk=pk)
    if request.method == "POST":
        policy.delete()
        messages.success(request, "Policy deleted.")
        return redirect("admin-view-policy")
    return render(
        request,
        "insurance/confirm_delete.html",
        {"object": policy, "title": "Delete policy", "cancel_url": "admin-view-policy"},
    )


# ---------------------------------------------------------------------------
# Admin: applications (PolicyRecord)
# ---------------------------------------------------------------------------
def _policy_holders(request, status=None):
    q = request.GET.get("q", "").strip()
    records = models.PolicyRecord.objects.select_related(
        "customer__user", "policy__category"
    )
    if status:
        records = records.filter(status=status)
    else:
        status_filter = request.GET.get("status", "").strip()
        if status_filter:
            records = records.filter(status=status_filter)
    if q:
        records = records.filter(
            Q(customer__user__first_name__icontains=q)
            | Q(customer__user__last_name__icontains=q)
            | Q(policy__policy_name__icontains=q)
        )
    return records, q


@staff_required
def admin_view_policy_holder_view(request):
    records, q = _policy_holders(request)
    return render(
        request,
        "insurance/admin_view_policy_holder.html",
        {
            "page_obj": paginate(request, records),
            "q": q,
            "statuses": models.PolicyRecord.Status.choices,
            "selected_status": request.GET.get("status", ""),
        },
    )


@staff_required
def admin_view_approved_policy_holder_view(request):
    records, q = _policy_holders(request, models.PolicyRecord.Status.APPROVED)
    return render(
        request,
        "insurance/admin_view_policy_holder.html",
        {"page_obj": paginate(request, records), "q": q, "heading": "Approved applications"},
    )


@staff_required
def admin_view_disapproved_policy_holder_view(request):
    records, q = _policy_holders(request, models.PolicyRecord.Status.DISAPPROVED)
    return render(
        request,
        "insurance/admin_view_policy_holder.html",
        {"page_obj": paginate(request, records), "q": q, "heading": "Disapproved applications"},
    )


@staff_required
def admin_view_waiting_policy_holder_view(request):
    records, q = _policy_holders(request, models.PolicyRecord.Status.PENDING)
    return render(
        request,
        "insurance/admin_view_policy_holder.html",
        {"page_obj": paginate(request, records), "q": q, "heading": "Pending applications"},
    )


@require_POST
@staff_required
def approve_request_view(request, pk):
    record = get_object_or_404(models.PolicyRecord, pk=pk)
    record.approve()
    models.Notification.notify(
        record.customer.user,
        f"Your application for '{record.policy.policy_name}' was approved.",
        url="/customer/history",
        kind=models.Notification.Kind.SUCCESS,
    )
    messages.success(request, "Application approved.")
    return redirect(request.POST.get("next") or "admin-view-policy-holder")


@require_POST
@staff_required
def disapprove_request_view(request, pk):
    record = get_object_or_404(models.PolicyRecord, pk=pk)
    record.disapprove()
    models.Notification.notify(
        record.customer.user,
        f"Your application for '{record.policy.policy_name}' was rejected.",
        url="/customer/history",
        kind=models.Notification.Kind.WARNING,
    )
    messages.success(request, "Application rejected.")
    return redirect(request.POST.get("next") or "admin-view-policy-holder")


# ---------------------------------------------------------------------------
# Admin: questions
# ---------------------------------------------------------------------------
@staff_required
def admin_question_view(request):
    q = request.GET.get("q", "").strip()
    answered = request.GET.get("answered", "").strip()
    questions = models.Question.objects.select_related("customer__user")
    if q:
        questions = questions.filter(
            Q(description__icontains=q)
            | Q(customer__user__first_name__icontains=q)
            | Q(customer__user__last_name__icontains=q)
        )
    if answered in {"0", "1"}:
        questions = questions.filter(is_answered=(answered == "1"))
    return render(
        request,
        "insurance/admin_question.html",
        {"page_obj": paginate(request, questions), "q": q, "answered": answered},
    )


@staff_required
def update_question_view(request, pk):
    question = get_object_or_404(models.Question.objects.select_related("customer__user"), pk=pk)
    form = forms.QuestionReplyForm(request.POST or None, instance=question)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.is_answered = True
        question.save()
        models.Notification.notify(
            question.customer.user,
            "An administrator replied to your question.",
            url="/customer/question-history",
        )
        messages.success(request, "Reply sent.")
        return redirect("admin-question")
    return render(request, "insurance/update_question.html", {"questionForm": form, "question": question})


# ---------------------------------------------------------------------------
# Admin: claims
# ---------------------------------------------------------------------------
@staff_required
def admin_claims_view(request):
    status = request.GET.get("status", "").strip()
    q = request.GET.get("q", "").strip()
    claims = models.Claim.objects.select_related(
        "customer__user", "policy_record__policy"
    )
    if status:
        claims = claims.filter(status=status)
    if q:
        claims = claims.filter(
            Q(customer__user__first_name__icontains=q)
            | Q(customer__user__last_name__icontains=q)
            | Q(policy_record__policy__policy_name__icontains=q)
        )
    return render(
        request,
        "insurance/admin_claims.html",
        {
            "page_obj": paginate(request, claims),
            "q": q,
            "statuses": models.Claim.Status.choices,
            "selected_status": status,
        },
    )


@staff_required
def admin_claim_detail_view(request, pk):
    claim = get_object_or_404(
        models.Claim.objects.select_related("customer__user", "policy_record__policy"),
        pk=pk,
    )
    form = forms.ClaimReviewForm(request.POST or None, instance=claim)
    if request.method == "POST" and form.is_valid():
        claim = form.save()
        models.Notification.notify(
            claim.customer.user,
            f"Your claim #{claim.pk} is now '{claim.get_status_display()}'.",
            url="/customer/claims",
            kind=models.Notification.Kind.SUCCESS
            if claim.status == models.Claim.Status.APPROVED
            else models.Notification.Kind.WARNING,
        )
        messages.success(request, "Claim updated.")
        return redirect("admin-claims")
    return render(request, "insurance/admin_claim_detail.html", {"form": form, "claim": claim})
