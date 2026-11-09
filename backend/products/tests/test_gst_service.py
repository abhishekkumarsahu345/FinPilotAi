"""Unit tests for the single GST math service (products/gst.py).

These are pure-function tests — no database access.
"""
from decimal import Decimal

from products.gst import (
    compute_line_tax_minor,
    split_line_tax,
    determine_place_of_supply,
    round_half_up_paise,
    rate_label,
    DEFAULT_GST_RATES,
)


# ---------------------------------------------------------------------------
# Rounding
# ---------------------------------------------------------------------------

class TestRounding:
    def test_round_half_up_basic(self):
        assert round_half_up_paise(Decimal("5999.94")) == 6000
        assert round_half_up_paise(Decimal("5999.5")) == 6000
        assert round_half_up_paise(Decimal("5999.4")) == 5999
        assert round_half_up_paise(Decimal("0.5")) == 1

    def test_round_half_up_zero(self):
        assert round_half_up_paise(Decimal("0")) == 0


# ---------------------------------------------------------------------------
# Per-line tax
# ---------------------------------------------------------------------------

class TestComputeLineTax:
    def test_18_percent(self):
        # ₹1000.00 (100000 paise) @ 18% -> ₹180.00 (18000 paise)
        assert compute_line_tax_minor(100_000, 1800) == 18_000

    def test_5_percent(self):
        # ₹1000.00 @ 5% -> ₹50.00 (5000 paise)
        assert compute_line_tax_minor(100_000, 500) == 5_000

    def test_no_gst(self):
        assert compute_line_tax_minor(100_000, 0) == 0

    def test_zero_taxable(self):
        assert compute_line_tax_minor(0, 1800) == 0

    def test_rounding_half_up(self):
        # 33333 * 1800 / 10000 = 5999.94 -> 6000 (half up)
        assert compute_line_tax_minor(33_333, 1800) == 6_000

    def test_quarter_percent(self):
        # ₹100.00 (10000 paise) @ 0.25% -> ₹0.25 (25 paise)
        assert compute_line_tax_minor(10_000, 25) == 25


# ---------------------------------------------------------------------------
# CGST/SGST/IGST split (cgst + sgst must always equal tax exactly)
# ---------------------------------------------------------------------------

class TestSplitLineTax:
    def test_intra_state_even(self):
        cgst, sgst, igst = split_line_tax(18_000, is_intra_state=True)
        assert (cgst, sgst, igst) == (9_000, 9_000, 0)
        assert cgst + sgst == 18_000

    def test_intra_state_odd(self):
        # Odd-paise total: cgst = tax//2, sgst = tax - cgst, sum exact
        cgst, sgst, igst = split_line_tax(1, is_intra_state=True)
        assert (cgst, sgst, igst) == (0, 1, 0)
        assert cgst + sgst == 1

    def test_inter_state(self):
        cgst, sgst, igst = split_line_tax(18_000, is_intra_state=False)
        assert (cgst, sgst, igst) == (0, 0, 18_000)

    def test_zero_tax(self):
        assert split_line_tax(0, True) == (0, 0, 0)
        assert split_line_tax(0, False) == (0, 0, 0)


# ---------------------------------------------------------------------------
# Place of supply
# ---------------------------------------------------------------------------

class TestPlaceOfSupply:
    def test_same_state_is_intra(self):
        is_intra, warning = determine_place_of_supply("07", "07")
        assert is_intra is True
        assert warning == ""

    def test_different_state_is_inter(self):
        is_intra, warning = determine_place_of_supply("07", "29")
        assert is_intra is False
        assert warning == ""

    def test_missing_org_state_fallback_intra_with_warning(self):
        is_intra, warning = determine_place_of_supply("", "29")
        assert is_intra is True
        assert warning != ""

    def test_missing_customer_state_fallback_intra_with_warning(self):
        is_intra, warning = determine_place_of_supply("07", "")
        assert is_intra is True
        assert warning != ""

    def test_both_missing_fallback_intra_with_warning(self):
        is_intra, warning = determine_place_of_supply("", "")
        assert is_intra is True
        assert warning != ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_rate_label(self):
        assert rate_label(1800) == "18%"
        assert rate_label(500) == "5%"
        assert rate_label(0) == "No GST"
        assert rate_label(25) == "0.25%"

    def test_default_rates_seeded(self):
        # 0, 5, 12, 18, 28 in basis points
        bps = [b for b, _ in DEFAULT_GST_RATES]
        assert bps == [0, 500, 1200, 1800, 2800]
