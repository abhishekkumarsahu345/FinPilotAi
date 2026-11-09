"""
Single source of truth for all GST math in FinPilot.

Everything that computes GST lives here. The frontend preview is display-only;
the backend recalculates and overrides on save using these functions.

Conventions
-----------
* Money is integer paise (`*_minor`). Never floats.
* GST rates are stored as integer basis points: 100 bps = 1%.
  e.g. 18% -> 1800, 5% -> 500, 0.25% -> 25, 0% (Nil) -> 0.
* One rounding policy: round-half-up to the nearest paise, per line.
* CGST + SGST must always equal the total tax exactly:
  cgst = tax // 2 ; sgst = tax - cgst  (handles odd-paise totals).
* Intra-state (org.state == customer.state) -> CGST + SGST.
* Inter-state (states differ)                      -> IGST.
* Missing state on either party -> fall back to intra-state, with a warning.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# Indian state codes (GST) — code -> display name.
# Used to populate the `state` field choices on Organization and Customer.
# Codes follow the GST state-code series (01–38).
# ---------------------------------------------------------------------------
INDIAN_STATES = [
    ("01", "Jammu & Kashmir"),
    ("02", "Himachal Pradesh"),
    ("03", "Punjab"),
    ("04", "Chandigarh"),
    ("05", "Uttarakhand"),
    ("06", "Haryana"),
    ("07", "Delhi"),
    ("08", "Rajasthan"),
    ("09", "Uttar Pradesh"),
    ("10", "Bihar"),
    ("11", "Sikkim"),
    ("12", "Arunachal Pradesh"),
    ("13", "Nagaland"),
    ("14", "Manipur"),
    ("15", "Mizoram"),
    ("16", "Tripura"),
    ("17", "Meghalaya"),
    ("18", "Assam"),
    ("19", "West Bengal"),
    ("20", "Jharkhand"),
    ("21", "Odisha"),
    ("22", "Chhattisgarh"),
    ("23", "Madhya Pradesh"),
    ("24", "Gujarat"),
    ("26", "Dadra & Nagar Haveli and Daman & Diu"),
    ("27", "Maharashtra"),
    ("29", "Karnataka"),
    ("30", "Goa"),
    ("31", "Lakshadweep"),
    ("32", "Kerala"),
    ("33", "Tamil Nadu"),
    ("34", "Puducherry"),
    ("35", "Andaman & Nicobar Islands"),
    ("36", "Telangana"),
    ("37", "Andhra Pradesh"),
    ("38", "Ladakh"),
]

STATE_CODE_CHOICES = [(code, name) for code, name in INDIAN_STATES]

# Sensible default GST rates (in basis points) seeded for new organizations.
DEFAULT_GST_RATES = [
    (0, "Nil rate"),
    (500, "5% GST"),
    (1200, "12% GST"),
    (1800, "18% GST"),
    (2800, "28% GST"),
]


def round_half_up_paise(value: Decimal) -> int:
    """Round a Decimal to an integer number of paise, half-up (Indian GST rule)."""
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_line_tax_minor(taxable_minor: int, rate_bps: int) -> int:
    """
    Total GST amount (paise) for one line.

    tax = round_half_up(taxable_minor * rate_bps / 10000)

    0 rate (No GST) or non-positive taxable -> 0 tax.
    """
    if rate_bps <= 0 or taxable_minor <= 0:
        return 0
    return round_half_up_paise(
        Decimal(taxable_minor) * Decimal(rate_bps) / Decimal(10000)
    )


def split_line_tax(tax_minor: int, is_intra_state: bool) -> tuple[int, int, int]:
    """
    Split a line's total tax into (cgst, sgst, igst) paise.

    Intra-state -> CGST + SGST (cgst = tax // 2, sgst = tax - cgst),
    so CGST + SGST always equals `tax_minor` exactly even for odd values.
    Inter-state -> IGST = full tax.
    """
    if tax_minor <= 0:
        return (0, 0, 0)
    if is_intra_state:
        cgst = tax_minor // 2
        sgst = tax_minor - cgst
        return (cgst, sgst, 0)
    return (0, 0, tax_minor)


def determine_place_of_supply(org_state: str, customer_state: str) -> tuple[bool, str]:
    """
    Decide intra vs inter-state place of supply.

    Returns (is_intra_state, warning). A missing state on either party falls
    back to intra-state (CGST+SGST) with a visible warning, per the requirement.
    """
    if not org_state or not customer_state:
        return (
            True,
            "Organization or customer state is missing; defaulting to "
            "intra-state (CGST + SGST). Set the state on both the organization "
            "and the customer to apply IGST correctly for inter-state sales.",
        )
    if org_state == customer_state:
        return (True, "")
    return (False, "")


def rate_label(rate_bps: int) -> str:
    """Human label for a rate in basis points, e.g. 1800 -> '18%'."""
    if rate_bps <= 0:
        return "No GST"
    # Basis points -> percent with up to 2 decimals, trailing zeros stripped.
    pct = Decimal(rate_bps) / Decimal(100)
    return f"{pct.normalize():g}%"


def create_default_gst_rates(org) -> None:
    """Seed the sensible default GST rates for a brand-new organization.

    Idempotent: skips any rate name that already exists for the org.
    Called from OrganizationSerializer.create and the register view.
    """
    from .models import GSTRate  # local import to avoid app-loading cycles

    existing = set(GSTRate.objects.filter(organization=org).values_list("name", flat=True))
    to_create = []
    for rate_bps, name in DEFAULT_GST_RATES:
        if name in existing:
            continue
        to_create.append(GSTRate(organization=org, name=name, rate_bps=rate_bps))
    if to_create:
        GSTRate.objects.bulk_create(to_create)
