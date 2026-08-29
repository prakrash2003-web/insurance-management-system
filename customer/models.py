from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    regex=r"^\+?[0-9]{7,15}$",
    message="Enter a valid phone number (7-15 digits, optional leading +).",
)


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer")
    profile_pic = models.ImageField(
        upload_to="profile_pic/Customer/", null=True, blank=True
    )
    address = models.CharField(max_length=200)
    mobile = models.CharField(max_length=16, validators=[phone_validator])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__first_name", "user__last_name"]

    @property
    def get_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username

    @property
    def get_id(self):
        return self.user.id

    def __str__(self):
        return self.get_name
