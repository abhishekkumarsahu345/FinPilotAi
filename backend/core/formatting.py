"""
Shared display-formatting helpers for FinPilot AI.

These functions are **display-only**: they never influence stored values,
calculations, GST, or totals.
"""
from decimal import Decimal, InvalidOperation
from typing import Union


def fmt_qty(value: Union[Decimal, float, int, str, None]) -> str:
    """
    Format a quantity for human display.

    Rules:
    - Whole numbers show with no decimals:   5.0000 → "5",  10.00 → "10"
    - Fractional values drop trailing zeros: 2.5000 → "2.5", 0.7500 → "0.75"
    - Never produces "5.", "-0", or scientific notation.
    - Handles None / empty string safely (returns "0").

    Examples:
        >>> fmt_qty(Decimal("5.0000"))
        '5'
        >>> fmt_qty(Decimal("2.5000"))
        '2.5'
        >>> fmt_qty(Decimal("0.7500"))
        '0.75'
        >>> fmt_qty(1)
        '1'
        >>> fmt_qty(None)
        '0'
        >>> fmt_qty("")
        '0'
    """
    if value is None or value == "":
        return "0"

    try:
        d = Decimal(str(value))
    except InvalidOperation:
        return "0"

    # Normalize removes trailing zeros and converts to canonical form,
    # but can produce scientific notation for very large/small numbers.
    # We handle that by using fixed-point string formatting when needed.
    normalized = d.normalize()

    # str(Decimal.normalize()) can yield "5E+3" for 5000.0000.
    # Convert to a plain string without scientific notation.
    sign, digits, exponent = normalized.as_tuple()
    if exponent >= 0:
        # Whole number — no decimal point needed.
        result = str(int(normalized))
    else:
        # Fractional — format with exactly the right number of decimal places.
        decimal_places = -exponent
        result = format(normalized, f".{decimal_places}f")

    # Safety: ensure we never return "-0"
    if result in ("-0", "-0.0"):
        return "0"

    return result
