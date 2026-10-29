import io
import csv

from django.db import transaction as db_transaction
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.models import Invoice, Payment, PaymentAllocation, Customer, AuditLog
from core.permissions import HasOrganizationAccess
from imports_app.models import ImportBatch, ImportRow
from imports_app.parsing import read_rows
from imports_app.storage import get_storage, sha256_hex
from django.conf import settings

from .models import BankTransaction, ReconciliationMatch
from .services import run_matching


# ---------------------------------------------------------------------------
# Bank statement upload
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def bank_statement_upload(request):
    """Upload a bank statement CSV/XLSX for normalization and matching."""
    org = request.membership.organization
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

    max_size = getattr(settings, "IMPORT_MAX_FILE_SIZE_BYTES", 10 * 1024 * 1024)
    if uploaded.size > max_size:
        return Response({"detail": "File exceeds 10 MB limit."}, status=status.HTTP_400_BAD_REQUEST)

    filename = uploaded.name
    if not (filename.lower().endswith(".csv") or filename.lower().endswith(".xlsx")):
        return Response({"detail": "Only CSV and XLSX files are accepted."}, status=400)

    file_bytes = uploaded.read()
    file_hash = sha256_hex(file_bytes)

    existing = ImportBatch.objects.filter(
        organization=org, file_hash=file_hash, batch_type=ImportBatch.BatchType.BANK_STATEMENT
    ).first()
    if existing:
        return Response({
            "batch_id": str(existing.id),
            "status": existing.status,
            "existing": True,
        })

    raw_rows, err = read_rows(file_bytes, filename)
    if err:
        return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)
    if not raw_rows:
        return Response({"detail": "File contains no data rows."}, status=400)

    file_ref = ""
    try:
        storage = get_storage()
        file_ref = f"bank-statements/{org.id}/{file_hash}/{filename}"
        storage.upload(file_ref, file_bytes)
    except Exception:
        pass

    batch = ImportBatch.objects.create(
        organization=org,
        batch_type=ImportBatch.BatchType.BANK_STATEMENT,
        file_name=filename,
        file_hash=file_hash,
        file_reference=file_ref,
        status=ImportBatch.Status.PREVIEW_READY,
        rows_total=len(raw_rows),
        created_by=request.user,
    )

    # Return detected column names for mapping confirmation
    detected_columns = list(raw_rows[0].keys()) if raw_rows else []
    sample_rows = raw_rows[:5]

    return Response({
        "batch_id": str(batch.id),
        "detected_columns": detected_columns,
        "sample_rows": sample_rows,
        "row_count": len(raw_rows),
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def bank_statement_confirm_mapping(request, batch_id):
    """
    Confirm column mapping and create BankTransaction staging rows.
    Body: {
        "mapping": {
            "transaction_date": "Date",
            "description": "Narration",
            "credit_amount": "Credit",
            "debit_amount": "Debit",
            "account_identifier": "Account"
        }
    }
    """
    org = request.membership.organization
    try:
        batch = ImportBatch.objects.get(
            id=batch_id, organization=org, batch_type=ImportBatch.BatchType.BANK_STATEMENT
        )
    except ImportBatch.DoesNotExist:
        return Response({"detail": "Batch not found."}, status=404)

    mapping = request.data.get("mapping", {})
    required = {"transaction_date", "description", "credit_amount", "debit_amount", "account_identifier"}
    missing = required - set(mapping.keys())
    if missing:
        return Response({"detail": f"Missing required column mappings: {missing}"}, status=400)

    # Download file and re-parse
    try:
        storage = get_storage()
        file_bytes = storage.download(batch.file_reference)
    except Exception:
        return Response({"detail": "Could not retrieve the uploaded file."}, status=500)

    from imports_app.parsing import read_rows, parse_date, to_minor
    raw_rows, err = read_rows(file_bytes, batch.file_name)
    if err:
        return Response({"detail": err}, status=400)

    # Normalize rows using the confirmed mapping
    created_count = skipped_count = 0
    duplicate_flags = []

    with db_transaction.atomic():
        batch.column_mapping = mapping
        batch.status = ImportBatch.Status.PROCESSING
        batch.save()

        for i, raw in enumerate(raw_rows, start=1):
            def col(canonical):
                col_name = mapping.get(canonical, canonical)
                return str(raw.get(col_name, "")).strip()

            txn_date, date_err = parse_date(col("transaction_date"))
            credit, credit_err = to_minor(col("credit_amount") or "0")
            debit, debit_err = to_minor(col("debit_amount") or "0")

            if date_err or credit_err or debit_err:
                skipped_count += 1
                continue

            account_id = col("account_identifier")
            description = col("description")
            ref = col("transaction_reference") if "transaction_reference" in mapping else ""

            # Duplicate detection
            is_dup = BankTransaction.objects.filter(
                organization=org,
                account_identifier=account_id,
                transaction_date=txn_date,
                credit_minor=credit,
                debit_minor=debit,
                transaction_reference=ref,
            ).exists()

            txn = BankTransaction.objects.create(
                organization=org,
                import_batch=batch,
                transaction_date=txn_date,
                description=description,
                transaction_reference=ref,
                account_identifier=account_id,
                debit_minor=debit,
                credit_minor=credit,
                currency=org.default_currency,
                is_probable_duplicate=is_dup,
            )
            created_count += 1
            if is_dup:
                duplicate_flags.append(i)

            # Auto-run matching if credit amount > 0
            if credit and credit > 0:
                run_matching(txn, org)

        batch.status = ImportBatch.Status.COMMITTED
        batch.rows_created = created_count
        batch.rows_skipped = skipped_count
        batch.completed_at = timezone.now()
        batch.save()

    AuditLog.objects.create(
        organization=org,
        actor=request.user,
        action="bank_statement.imported",
        entity_type="import_batch",
        entity_id=str(batch.id),
        summary=f"Imported bank statement: {created_count} rows, {skipped_count} skipped",
    )

    return Response({
        "batch_id": str(batch.id),
        "created": created_count,
        "skipped": skipped_count,
        "probable_duplicates": duplicate_flags,
    })


# ---------------------------------------------------------------------------
# Reconciliation matches
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def reconciliation_list(request):
    """List reconciliation matches pending review."""
    org = request.membership.organization
    matches = (
        ReconciliationMatch.objects.filter(
            organization=org,
            status=ReconciliationMatch.MatchStatus.SUGGESTED,
        )
        .select_related("transaction", "invoice__customer", "payment")
        .order_by("-confidence_score")[:100]
    )
    return Response([
        {
            "id": str(m.id),
            "transaction": {
                "id": str(m.transaction.id),
                "date": str(m.transaction.transaction_date),
                "description": m.transaction.description[:200],
                "credit_minor": m.transaction.credit_minor,
                "available_minor": m.transaction.available_minor(),
            },
            "invoice": {
                "id": str(m.invoice.id),
                "invoice_number": m.invoice.invoice_number,
                "customer": m.invoice.customer.name,
            } if m.invoice else None,
            "suggested_amount_minor": m.suggested_amount_minor,
            "confidence_score": m.confidence_score,
            "is_deterministic": m.is_deterministic,
            "evidence": m.match_evidence,
        }
        for m in matches
    ])


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def confirm_match(request, match_id):
    """
    Confirm a reconciliation match — creates a Payment + PaymentAllocation.
    """
    org = request.membership.organization
    try:
        match = ReconciliationMatch.objects.select_related(
            "transaction", "invoice__customer"
        ).get(id=match_id, organization=org)
    except ReconciliationMatch.DoesNotExist:
        return Response({"detail": "Match not found."}, status=404)

    if match.status != ReconciliationMatch.MatchStatus.SUGGESTED:
        return Response({"detail": f"Match is in status '{match.status}'."}, status=400)

    txn = match.transaction
    inv = match.invoice
    amount = match.suggested_amount_minor

    if amount > txn.available_minor():
        return Response(
            {"detail": f"Suggested amount exceeds available transaction amount."},
            status=400,
        )

    # Validate invoice balance
    active_paid = sum(
        a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
    )
    balance = max(0, inv.total_minor - active_paid)
    if amount > balance:
        return Response(
            {"detail": f"Suggested amount exceeds invoice outstanding balance."},
            status=400,
        )

    with db_transaction.atomic():
        # Create payment record from the bank transaction
        payment = Payment.objects.create(
            organization=org,
            customer=inv.customer,
            payment_date=txn.transaction_date,
            amount_minor=amount,
            currency=txn.currency,
            method=Payment.Method.BANK_TRANSFER,
            reference=txn.transaction_reference or str(txn.id)[:20],
            notes=f"Reconciled from bank statement import batch {txn.import_batch_id}",
            source="reconciliation",
            recorded_by=request.user,
        )
        alloc = PaymentAllocation.objects.create(
            organization=org,
            payment=payment,
            invoice=inv,
            amount_minor=amount,
            created_by=request.user,
        )
        # Update transaction allocated amount
        txn.allocated_minor += amount
        if txn.allocated_minor >= txn.credit_minor:
            txn.reconciliation_status = BankTransaction.ReconciliationStatus.CONFIRMED
        txn.save()

        match.status = ReconciliationMatch.MatchStatus.CONFIRMED
        match.payment = payment
        match.payment_allocation = alloc
        match.reviewed_by = request.user
        match.reviewed_at = timezone.now()
        match.save()

        AuditLog.objects.create(
            organization=org,
            actor=request.user,
            action="reconciliation.confirmed",
            entity_type="reconciliation_match",
            entity_id=str(match.id),
            summary=(
                f"Confirmed reconciliation: ₹{amount/100:.2f} "
                f"from transaction {txn.id} to invoice {inv.invoice_number}"
            ),
        )

    return Response({"detail": "Match confirmed and payment allocation created."})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def reject_match(request, match_id):
    """Reject a reconciliation match suggestion."""
    org = request.membership.organization
    try:
        match = ReconciliationMatch.objects.get(id=match_id, organization=org)
    except ReconciliationMatch.DoesNotExist:
        return Response({"detail": "Match not found."}, status=404)

    with db_transaction.atomic():
        match.status = ReconciliationMatch.MatchStatus.REJECTED
        match.reviewed_by = request.user
        match.reviewed_at = timezone.now()
        match.save()
        AuditLog.objects.create(
            organization=org,
            actor=request.user,
            action="reconciliation.rejected",
            entity_type="reconciliation_match",
            entity_id=str(match.id),
            summary=f"Rejected reconciliation match {match.id}",
        )
    return Response({"detail": "Match rejected."})
