"""Transparent, rule-based domain logic.

Nothing here is machine learning: every number is produced by explicit,
inspectable rules so results can be explained to the end user.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings

# --- Premium calculator ----------------------------------------------------

AGE_FACTORS = [
    (0, 25, Decimal("0.90")),
    (25, 36, Decimal("1.00")),
    (36, 46, Decimal("1.20")),
    (46, 56, Decimal("1.50")),
    (56, 66, Decimal("2.00")),
    (66, 200, Decimal("2.80")),
]

CATEGORY_FACTORS = {
    "health": Decimal("1.20"),
    "medical": Decimal("1.20"),
    "vehicle": Decimal("1.10"),
    "motor": Decimal("1.10"),
    "car": Decimal("1.10"),
    "life": Decimal("1.00"),
    "term": Decimal("1.00"),
    "travel": Decimal("0.80"),
    "home": Decimal("0.90"),
    "property": Decimal("0.90"),
}


def _age_factor(age):
    for lo, hi, factor in AGE_FACTORS:
        if lo <= age < hi:
            return factor
    return Decimal("1.00")


def _category_factor(category_name):
    if not category_name:
        return Decimal("1.00")
    name = category_name.lower()
    for key, factor in CATEGORY_FACTORS.items():
        if key in name:
            return factor
    return Decimal("1.00")


def calculate_premium(*, age, sum_assured, tenure, category_name=None, smoker=False):
    """Return an estimated annual premium plus a full factor breakdown."""
    base_rate = Decimal(str(settings.PREMIUM_CALCULATOR_BASE_RATE))
    sum_assured = Decimal(str(sum_assured))
    tenure = int(tenure)

    annual_base = (sum_assured * base_rate).quantize(Decimal("0.01"))
    age_factor = _age_factor(int(age))
    tenure_factor = (Decimal("1.00") - Decimal("0.005") * min(tenure, 30)).quantize(
        Decimal("0.0001")
    )
    smoker_factor = Decimal("1.30") if smoker else Decimal("1.00")
    category_factor = _category_factor(category_name)

    estimated = (
        annual_base * age_factor * tenure_factor * smoker_factor * category_factor
    ).quantize(Decimal("0.01"))

    breakdown = [
        ("Base premium", f"{sum_assured:,.0f} x {base_rate} base rate", f"{annual_base:,.2f}"),
        ("Age factor", f"age {int(age)}", f"x {age_factor}"),
        ("Tenure factor", f"{tenure} year(s)", f"x {tenure_factor}"),
        ("Smoker factor", "smoker" if smoker else "non-smoker", f"x {smoker_factor}"),
        ("Category factor", category_name or "generic", f"x {category_factor}"),
    ]
    return {
        "estimated_annual_premium": estimated,
        "estimated_monthly_premium": (estimated / 12).quantize(Decimal("0.01")),
        "total_over_tenure": (estimated * tenure).quantize(Decimal("0.01")),
        "breakdown": breakdown,
    }


# --- Rule-based policy recommendation ------------------------------------


@dataclass
class Recommendation:
    policy: object
    score: int = 0
    reasons: list = field(default_factory=list)

    @property
    def match_label(self):
        if self.score >= 75:
            return "Excellent match"
        if self.score >= 50:
            return "Good match"
        if self.score >= 25:
            return "Partial match"
        return "Weak match"


def recommend_policies(
    policies, *, age, annual_income, dependents, desired_coverage, category_name=None
):
    """Score every policy against the customer's profile.

    Returns a list of ``Recommendation`` objects sorted best-first. Only
    policies scoring above zero are returned.
    """
    age = int(age)
    annual_income = Decimal(str(annual_income))
    dependents = int(dependents)
    desired_coverage = Decimal(str(desired_coverage))
    affordable_premium = annual_income * Decimal("0.15")

    results = []
    for policy in policies:
        rec = Recommendation(policy=policy)

        # 1. Coverage match (max 35)
        if desired_coverage > 0:
            ratio = Decimal(policy.sum_assurance) / desired_coverage
            if Decimal("0.8") <= ratio <= Decimal("1.5"):
                rec.score += 35
                rec.reasons.append(
                    f"Coverage of {policy.sum_assurance:,} closely matches your "
                    f"requested {desired_coverage:,.0f}"
                )
            elif Decimal("0.5") <= ratio < Decimal("0.8"):
                rec.score += 18
                rec.reasons.append("Coverage is a little below what you asked for")
            elif Decimal("1.5") < ratio <= Decimal("3"):
                rec.score += 15
                rec.reasons.append("Coverage is higher than requested (extra protection)")

        # 2. Premium affordability (max 30)
        if affordable_premium > 0:
            if policy.premium <= affordable_premium:
                headroom = (affordable_premium - policy.premium) / affordable_premium
                rec.score += int(15 + 15 * min(headroom, Decimal("1")))
                rec.reasons.append(
                    f"Annual premium {policy.premium:,} fits within ~15% of your income "
                    f"({affordable_premium:,.0f})"
                )
            elif policy.premium <= affordable_premium * Decimal("1.25"):
                rec.score += 8
                rec.reasons.append("Premium is slightly above the comfortable range")

        # 3. Tenure suitability by age (max 20)
        if age < 35 and policy.tenure >= 15:
            rec.score += 20
            rec.reasons.append("Long tenure suits your age group")
        elif 35 <= age <= 50 and 10 <= policy.tenure <= 20:
            rec.score += 20
            rec.reasons.append("Medium tenure suits your age group")
        elif age > 50 and policy.tenure <= 10:
            rec.score += 20
            rec.reasons.append("Shorter tenure suits your age group")
        elif 8 <= policy.tenure <= 25:
            rec.score += 8

        # 4. Dependents (max 10)
        if dependents >= 2 and Decimal(policy.sum_assurance) >= desired_coverage:
            rec.score += 10
            rec.reasons.append(
                f"Sufficient cover for {dependents} dependents"
            )
        elif dependents <= 1:
            rec.score += 5

        # 5. Category match (max 5)
        if category_name and category_name.lower() in policy.category.category_name.lower():
            rec.score += 5
            rec.reasons.append(f"Category matches your requirement ({category_name})")

        rec.score = max(0, min(100, rec.score))
        if rec.score > 0:
            results.append(rec)

    results.sort(key=lambda r: r.score, reverse=True)
    return results
