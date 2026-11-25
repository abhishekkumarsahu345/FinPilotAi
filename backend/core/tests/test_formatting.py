"""
Unit tests for core.formatting helpers.

Run with:  pytest backend/core/tests/test_formatting.py -v
"""
import pytest
from decimal import Decimal
from core.formatting import fmt_qty


class TestFmtQty:
    """Tests for the fmt_qty display helper."""

    # --- Whole numbers ---
    def test_whole_number_decimal_no_decimal_point(self):
        assert fmt_qty(Decimal("5.0000")) == "5"

    def test_whole_number_two_decimal_zeros(self):
        assert fmt_qty(Decimal("10.00")) == "10"

    def test_whole_number_one(self):
        assert fmt_qty(Decimal("1.0000")) == "1"

    def test_whole_number_int(self):
        assert fmt_qty(1) == "1"

    def test_whole_number_float(self):
        assert fmt_qty(10.0) == "10"

    def test_whole_number_zero(self):
        assert fmt_qty(Decimal("0.0000")) == "0"

    def test_whole_number_zero_int(self):
        assert fmt_qty(0) == "0"

    def test_large_whole_number(self):
        assert fmt_qty(Decimal("10000.0000")) == "10000"

    # --- One decimal place ---
    def test_one_decimal_place(self):
        assert fmt_qty(Decimal("2.5000")) == "2.5"

    def test_one_decimal_place_exact_half(self):
        assert fmt_qty(Decimal("0.5000")) == "0.5"

    # --- Two decimal places ---
    def test_two_decimal_places(self):
        assert fmt_qty(Decimal("0.7500")) == "0.75"

    def test_two_decimal_places_1_25(self):
        assert fmt_qty(Decimal("1.2500")) == "1.25"

    def test_two_decimal_places_no_trailing_zeros(self):
        assert fmt_qty(Decimal("3.1000")) == "3.1"

    # --- Three decimal places ---
    def test_three_decimal_places(self):
        assert fmt_qty(Decimal("1.1250")) == "1.125"

    # --- Four decimal places ---
    def test_four_decimal_places(self):
        assert fmt_qty(Decimal("1.0001")) == "1.0001"

    def test_four_decimal_places_no_trailing_zero(self):
        assert fmt_qty(Decimal("2.1230")) == "2.123"

    # --- String input ---
    def test_string_whole(self):
        assert fmt_qty("5.0000") == "5"

    def test_string_fractional(self):
        assert fmt_qty("2.5000") == "2.5"

    # --- Edge cases ---
    def test_none_returns_zero(self):
        assert fmt_qty(None) == "0"

    def test_empty_string_returns_zero(self):
        assert fmt_qty("") == "0"

    def test_very_large_number(self):
        result = fmt_qty(Decimal("999999.0000"))
        assert result == "999999"

    def test_very_large_fractional(self):
        result = fmt_qty(Decimal("999999.5000"))
        assert result == "999999.5"

    def test_negative_zero_not_returned(self):
        # Negative quantities shouldn't appear in practice, but guard "-0"
        result = fmt_qty(Decimal("-0.0000"))
        assert result == "0"

    def test_no_scientific_notation_large(self):
        # Decimal.normalize() of "10000.0000" could produce "1E+4"; we must not
        result = fmt_qty(Decimal("10000.0000"))
        assert "E" not in result
        assert result == "10000"

    def test_no_trailing_dot(self):
        # Must never return something like "5."
        for v in ["1.0", "2.0000", "100.00"]:
            result = fmt_qty(v)
            assert not result.endswith("."), f"Got trailing dot for input {v!r}: {result!r}"
