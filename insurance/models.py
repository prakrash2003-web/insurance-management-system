from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from customer.models import Customer


class Category(models.Model):
    category_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category_name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.category_name


class Policy(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="policies"
    )
    policy_name = models.CharField(max_length=200)
    sum_assurance = models.PositiveIntegerField(
        validators=[MinValueValidator(1000)],
        help_text="Total amount assured, in currency units.",
    )
    premium = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Annual premium, in currency units.",
    )
    tenure = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Policy duration in years.",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["policy_name"]
        verbose_name_plural = "policies"

    def __str__(self):
        return self.policy_name

    @property
    def annual_premium_rate(self):
        """Premium as a fraction of the sum assured (used for comparisons)."""
        if self.sum_assurance:
            return round(self.premium / self.sum_assurance, 4)
        return 0


class PolicyRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        APPROVED = "Approved", "Approved"
        DISAPPROVED = "Disapproved", "Disapproved"

    class RenewalStatus(models.TextChoices):
        NOT_APPLICABLE = "NotApplicable", "Not applicable"
        ACTIVE = "Active", "Active"
        DUE = "Due", "Due for renewal"
        EXPIRED = "Expired", "Expired"
        RENEWED = "Renewed", "Renewed"

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="policy_records"
    )
    policy = models.ForeignKey(
        Policy, on_delete=models.CASCADE, related_name="records"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    renewal_reminder_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer.get_name} - {self.policy.policy_name} ({self.status})"

    # --- lifecycle helpers ------------------------------------------------
    def approve(self):
        self.status = self.Status.APPROVED
        self.start_date = timezone.now().date()
        self.end_date = self.start_date + timedelta(days=365 * self.policy.tenure)
        self.save()

    def disapprove(self):
        self.status = self.Status.DISAPPROVED
        self.start_date = None
        self.end_date = None
        self.save()

    # --- renewal / expiry -----------------------------------------------
    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    @property
    def days_to_expiry(self):
        if not self.end_date:
            return None
        return (self.end_date - timezone.now().date()).days

    @property
    def is_expired(self):
        d = self.days_to_expiry
        return d is not None and d < 0

    @property
    def needs_renewal(self):
        d = self.days_to_expiry
        return d is not None and 0 <= d <= 30

    @property
    def renewal_status(self):
        if not self.is_approved or not self.end_date:
            return self.RenewalStatus.NOT_APPLICABLE
        if self.is_expired:
            return self.RenewalStatus.EXPIRED
        if self.needs_renewal:
            return self.RenewalStatus.DUE
        return self.RenewalStatus.ACTIVE


class Question(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="questions"
    )
    description = models.CharField(max_length=500)
    admin_comment = models.CharField(max_length=500, blank=True, default="")
    is_answered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Q{self.pk} by {self.customer.get_name}"


class Claim(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        APPROVED = "Approved", "Approved"
        REJECTED = "Rejected", "Rejected"

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="claims"
    )
    policy_record = models.ForeignKey(
        PolicyRecord, on_delete=models.CASCADE, related_name="claims"
    )
    claim_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(1)]
    )
    description = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    admin_remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Claim {self.pk} - {self.policy_record.policy.policy_name} ({self.status})"

    @property
    def policy(self):
        return self.policy_record.policy


class Notification(models.Model):
    class Kind(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"

    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.INFO)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"To {self.user}: {self.message}"

    @classmethod
    def notify(cls, user, message, url="", kind=Kind.INFO):
        if user is None:
            return None
        return cls.objects.create(user=user, message=message, url=url, kind=kind)
