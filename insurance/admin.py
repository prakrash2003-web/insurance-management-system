from django.contrib import admin

from . import models


@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("category_name", "created_at", "updated_at")
    search_fields = ("category_name",)


@admin.register(models.Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = (
        "policy_name",
        "category",
        "sum_assurance",
        "premium",
        "tenure",
        "is_active",
    )
    list_filter = ("category", "is_active")
    search_fields = ("policy_name",)


@admin.register(models.PolicyRecord)
class PolicyRecordAdmin(admin.ModelAdmin):
    list_display = ("customer", "policy", "status", "start_date", "end_date", "created_at")
    list_filter = ("status",)
    search_fields = ("customer__user__username", "policy__policy_name")
    date_hierarchy = "created_at"


@admin.register(models.Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("customer", "is_answered", "created_at")
    list_filter = ("is_answered",)


@admin.register(models.Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "policy", "claim_amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("customer__user__username",)
    date_hierarchy = "created_at"


@admin.register(models.Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")
