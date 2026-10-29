"""
Reconciliation matching service.
Stage 1: deterministic rules (exact matches).
Stage 2: fuzzy scoring (suggestions only).
Confirmed matches create PaymentAllocations through the normal payment workflow.
"""
from datetime import timedelta
from difflib import SequenceMatcher

from core.models import Invoice


def _amount_close(a: int, b: int, tolerance_pct: float = 0.01) -> bool:
    if b == 0:
        return a == 0
    return abs(a - b) / b <= tolerance_pct


def _text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def run_matching(transaction, org):
    """
    Generate ReconciliationMatch suggestions for a BankTransaction.
    Returns list of created ReconciliationMatch objects.
    """
    from .models import ReconciliationMatch

    available = transaction.available_minor()
    if available <= 0:
        return []

    # Only match against issued invoices with outstanding balance
    invoices = (
        Invoice.objects.filter(organization=org, status=Invoice.Status.ISSUED)
        .select_related("customer")
        .prefetch_related("allocations")
    )

    # Pre-compute balances
    candidates = []
    for inv in invoices:
        balance = max(0, inv.total_minor - sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        ))
        if balance > 0:
            candidates.append((inv, balance))

    description = transaction.description.lower()
    ref = (transaction.transaction_reference or "").lower()
    matches_created = []

    for inv, balance in candidates:
        score = 0.0
        evidence = []
        is_deterministic = False

        # ── Deterministic signals ─────────────────────────────────────────
        inv_num = inv.invoice_number.lower()
        if inv_num in description or inv_num in ref:
            score += 0.5
            evidence.append({"signal": "invoice_number_in_narration", "detail": inv.invoice_number})
            is_deterministic = True

        if ref and ref == inv_num:
            score += 0.3
            evidence.append({"signal": "exact_reference_match", "detail": ref})
            is_deterministic = True

        if transaction.credit_minor == balance:
            score += 0.3
            evidence.append({"signal": "exact_amount_match", "detail": f"₹{balance/100:.2f}"})

        if transaction.credit_minor == inv.total_minor:
            score += 0.1
            evidence.append({"signal": "matches_invoice_total", "detail": f"₹{inv.total_minor/100:.2f}"})

        # Customer name in description
        cust_name_sim = _text_similarity(inv.customer.name, description)
        if cust_name_sim > 0.6:
            score += 0.2
            evidence.append({"signal": "customer_name_similarity", "detail": f"{cust_name_sim:.0%}"})

        # ── Fuzzy signals ─────────────────────────────────────────────────
        if not is_deterministic:
            # Amount within 1%
            if _amount_close(transaction.credit_minor, balance):
                score += 0.15
                evidence.append({"signal": "approximate_amount_match", "detail": "within 1%"})

            # Date proximity (transaction date within 3 days of due date)
            days_diff = abs((transaction.transaction_date - inv.due_date).days)
            if days_diff <= 3:
                score += 0.1
                evidence.append({"signal": "date_proximity", "detail": f"{days_diff} day(s) from due date"})

        if score < 0.1 or not evidence:
            continue

        # Cap suggested amount at available transaction amount
        suggested = min(balance, available)

        match = ReconciliationMatch.objects.create(
            organization=org,
            transaction=transaction,
            invoice=inv,
            suggested_amount_minor=suggested,
            confidence_score=min(score, 1.0),
            match_evidence=evidence,
            is_deterministic=is_deterministic,
            status=ReconciliationMatch.MatchStatus.SUGGESTED,
        )
        matches_created.append(match)

    # Mark transaction as having suggestions
    if matches_created:
        transaction.reconciliation_status = "suggested"
        transaction.save()

    return matches_created
