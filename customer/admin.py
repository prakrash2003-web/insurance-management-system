from django.contrib import admin

from . import models


@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("get_name", "mobile", "created_at")
    search_fields = ("user__username", "user__first_name", "user__last_name", "mobile")
