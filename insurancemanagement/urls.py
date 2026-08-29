from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic.base import RedirectView

from insurance import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("customer/", include("customer.urls")),

    path(
        "favicon.ico",
        RedirectView.as_view(url=settings.STATIC_URL + "favicon.svg", permanent=True),
    ),

    path("", views.home_view, name="home"),
    path("aboutus", views.aboutus_view, name="aboutus"),
    path("contactus", views.contactus_view, name="contactus"),
    path("afterlogin", views.afterlogin_view, name="afterlogin"),
    path("premium-calculator", views.premium_calculator_view, name="premium-calculator"),

    # --- Authentication -------------------------------------------------
    path("adminlogin", views.AdminLoginView.as_view(), name="adminlogin"),
    path("logout", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "password-change",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url="/password-change/done",
        ),
        name="password_change",
    ),
    path(
        "password-change/done",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),
    path(
        "password-reset",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            success_url="/password-reset/done",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url="/reset/done/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # --- Admin dashboard ----------------------------------------------
    path("admin-dashboard", views.admin_dashboard_view, name="admin-dashboard"),
    path("notifications", views.notifications_view, name="notifications"),
    path("notifications/read/<int:pk>", views.notification_read_view, name="notification-read"),
    path("notifications/read-all", views.notification_read_all_view, name="notification-read-all"),

    path("admin-view-customer", views.admin_view_customer_view, name="admin-view-customer"),
    path("update-customer/<int:pk>", views.update_customer_view, name="update-customer"),
    path("delete-customer/<int:pk>", views.delete_customer_view, name="delete-customer"),

    path("admin-category", views.admin_category_view, name="admin-category"),
    path("admin-view-category", views.admin_view_category_view, name="admin-view-category"),
    path("admin-add-category", views.admin_add_category_view, name="admin-add-category"),
    path("update-category/<int:pk>", views.update_category_view, name="update-category"),
    path("delete-category/<int:pk>", views.delete_category_view, name="delete-category"),

    path("admin-policy", views.admin_policy_view, name="admin-policy"),
    path("admin-add-policy", views.admin_add_policy_view, name="admin-add-policy"),
    path("admin-view-policy", views.admin_view_policy_view, name="admin-view-policy"),
    path("update-policy/<int:pk>", views.update_policy_view, name="update-policy"),
    path("delete-policy/<int:pk>", views.delete_policy_view, name="delete-policy"),

    path("admin-view-policy-holder", views.admin_view_policy_holder_view, name="admin-view-policy-holder"),
    path("admin-view-approved-policy-holder", views.admin_view_approved_policy_holder_view, name="admin-view-approved-policy-holder"),
    path("admin-view-disapproved-policy-holder", views.admin_view_disapproved_policy_holder_view, name="admin-view-disapproved-policy-holder"),
    path("admin-view-waiting-policy-holder", views.admin_view_waiting_policy_holder_view, name="admin-view-waiting-policy-holder"),
    path("approve-request/<int:pk>", views.approve_request_view, name="approve-request"),
    path("reject-request/<int:pk>", views.disapprove_request_view, name="reject-request"),

    path("admin-question", views.admin_question_view, name="admin-question"),
    path("update-question/<int:pk>", views.update_question_view, name="update-question"),

    path("admin-claims", views.admin_claims_view, name="admin-claims"),
    path("admin-claim/<int:pk>", views.admin_claim_detail_view, name="admin-claim-detail"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
