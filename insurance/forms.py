from django import forms
from django.contrib.auth.models import User

from . import models


class ContactusForm(forms.Form):
    name = forms.CharField(max_length=60)
    email = forms.EmailField()
    message = forms.CharField(
        max_length=1000, widget=forms.Textarea(attrs={"rows": 4})
    )


class AdminCustomerUpdateForm(forms.ModelForm):
    """Admin edit of a customer's login account. No password field -> the
    previous 're-hash the hash and lock the user out' bug cannot occur."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_active"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email


class CategoryForm(forms.ModelForm):
    class Meta:
        model = models.Category
        fields = ["category_name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class PolicyForm(forms.ModelForm):
    class Meta:
        model = models.Policy
        fields = [
            "category",
            "policy_name",
            "sum_assurance",
            "premium",
            "tenure",
            "description",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        premium = cleaned.get("premium")
        sum_assurance = cleaned.get("sum_assurance")
        if premium and sum_assurance and premium >= sum_assurance:
            self.add_error(
                "premium", "Premium must be smaller than the sum assured."
            )
        return cleaned


class QuestionForm(forms.ModelForm):
    class Meta:
        model = models.Question
        fields = ["description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}


class QuestionReplyForm(forms.ModelForm):
    class Meta:
        model = models.Question
        fields = ["admin_comment"]
        widgets = {"admin_comment": forms.Textarea(attrs={"rows": 4})}

    def clean_admin_comment(self):
        comment = self.cleaned_data["admin_comment"].strip()
        if not comment:
            raise forms.ValidationError("A reply cannot be empty.")
        return comment


class ClaimForm(forms.ModelForm):
    class Meta:
        model = models.Claim
        fields = ["policy_record", "claim_amount", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, customer=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = models.PolicyRecord.objects.filter(
            status=models.PolicyRecord.Status.APPROVED
        ).select_related("policy")
        if customer is not None:
            qs = qs.filter(customer=customer)
        self.fields["policy_record"].queryset = qs
        self.fields["policy_record"].label = "Approved policy"

    def clean(self):
        cleaned = super().clean()
        record = cleaned.get("policy_record")
        amount = cleaned.get("claim_amount")
        if record and amount and amount > record.policy.sum_assurance:
            self.add_error(
                "claim_amount",
                "Claim amount cannot exceed the policy's sum assured "
                f"({record.policy.sum_assurance:,}).",
            )
        return cleaned


class ClaimReviewForm(forms.ModelForm):
    class Meta:
        model = models.Claim
        fields = ["status", "admin_remarks"]
        widgets = {"admin_remarks": forms.Textarea(attrs={"rows": 4})}


class PremiumCalculatorForm(forms.Form):
    age = forms.IntegerField(min_value=18, max_value=99)
    sum_assured = forms.IntegerField(min_value=1000, label="Desired sum assured")
    tenure = forms.IntegerField(min_value=1, max_value=100, label="Tenure (years)")
    category = forms.ModelChoiceField(
        queryset=models.Category.objects.all(), required=False, empty_label="Generic"
    )
    smoker = forms.BooleanField(required=False)


class RecommendationForm(forms.Form):
    age = forms.IntegerField(min_value=18, max_value=99)
    annual_income = forms.IntegerField(min_value=1)
    dependents = forms.IntegerField(min_value=0, max_value=20)
    desired_coverage = forms.IntegerField(min_value=1000)
    category = forms.ModelChoiceField(
        queryset=models.Category.objects.all(),
        required=False,
        empty_label="Any category",
    )
