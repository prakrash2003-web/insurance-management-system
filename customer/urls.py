from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("customerclick", views.customerclick_view, name="customerclick"),
    path("customersignup", views.customer_signup_view, name="customersignup"),
    path(
        "customerlogin",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="customerlogin",
    ),

    path("customer-dashboard", views.customer_dashboard_view, name="customer-dashboard"),
    path("profile", views.customer_profile_view, name="customer-profile"),
    path("profile/edit", views.customer_profile_edit_view, name="customer-profile-edit"),

    path("policies", views.policy_list_view, name="policy-list"),
    path("policies/compare", views.policy_compare_view, name="policy-compare"),
    path("policy/<int:pk>", views.policy_detail_view, name="policy-detail"),
    path("apply/<int:pk>", views.apply_view, name="apply"),

    path("history", views.application_history_view, name="history"),
    path("application/<int:pk>", views.application_detail_view, name="application-detail"),

    path("renewals", views.renewal_view, name="renewals"),
    path("renew/<int:pk>", views.renew_view, name="renew"),

    path("ask-question", views.ask_question_view, name="ask-question"),
    path("question-history", views.question_history_view, name="question-history"),

    path("claims", views.claim_list_view, name="claim-list"),
    path("claims/new", views.claim_create_view, name="claim-create"),
    path("claim/<int:pk>", views.claim_detail_view, name="claim-detail"),

    path("recommendations", views.recommendation_view, name="recommendations"),
]
