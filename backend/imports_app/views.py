import io
import csv

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.models import Invoice, Customer, AuditLog
from core.permissions import HasOrganizationAccess

from .models import ImportBatch, ImportRow
from .parsing import read_rows, validate_invoice_row
from .storage import get_storage, sha256_hex

import openpyxl


# ---------------------------------------------------------------------------
# Invoice import template
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def invoice_template_csv(request):
    """Download a sample CSV invoice import template."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="invoice_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "invoice_number", "invoice_date", "due_date", "customer_name",
        "subtotal", "discount", "tax", "total", "currency", "notes",
    ])
    writer.writerow([
        "INV-2026-001", "2026-10-01", "2026-10-31",
        "Acme Industries", "10000.00", "0.00", "1800.00", "11800.00", "INR",
        "Q3 services",
    ])
    return response


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def invoice_template_xlsx(request):
    """Download a sample XLSX invoice import template."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Invoices"
    headers = [
        "invoice_number", "invoice_date", "due_date", "customer_name",
        "subtotal", "discount", "tax", "total", "currency", "notes",
    ]
    ws.append(headers)
    ws.append([
        "INV-2026-001", "2026-10-01", "2026-10-31",
        "Acme Industries", 10000.00, 0.00, 1800.00, 11800.00, "INR", "Q3 services",
    ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="invoice_import_template.xlsx"'
    return response


# ---------------------------------------------------------------------------
# Invoice import: upload → preview
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def invoice_upload(request):
    """
    Upload an invoice CSV/XLSX file.
    Validates, parses, creates ImportBatch + ImportRows with preview status.
    Returns batch_id + row preview immediately (no Celery needed at this scale).
    """
    org = request.membership.organization
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

    # Size check
    max_size = getattr(settings, "IMPORT_MAX_FILE_SIZE_BYTES", 10 * 1024 * 1024)
    if uploaded.size > max_size:
        return Response(
            {"detail": f"File exceeds maximum size of {max_size // (1024 * 1024)} MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    filename = uploaded.name
    file_bytes = uploaded.read()

    # File type check by extension (magic byte check would require python-magic)
    if not (filename.lower().endswith(".csv") or filename.lower().endswith(".xlsx")):
        return Response(
            {"detail": "Only CSV and XLSX files are accepted."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Deduplication by SHA-256 hash
    file_hash = sha256_hex(file_bytes)
    existing_batch = ImportBatch.objects.filter(
        organization=org,
        file_hash=file_hash,
        batch_type=ImportBatch.BatchType.INVOICE,
    ).first()
    if existing_batch:
        rows = ImportRow.objects.filter(batch=existing_batch)
        return Response({
            "batch_id": str(existing_batch.id),
            "status": existing_batch.status,
            "existing": True,
            "rows": _serialize_rows(rows),
        })

    # Parse rows
    raw_rows, parse_error = read_rows(file_bytes, filename)
    if parse_error:
        batch = ImportBatch.objects.create(
            organization=org,
            batch_type=ImportBatch.BatchType.INVOICE,
            file_name=filename,
            file_hash=file_hash,
            status=ImportBatch.Status.FAILED,
            error_summary=parse_error,
            created_by=request.user,
        )
        return Response(
            {"batch_id": str(batch.id), "detail": parse_error},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Store file in S3 (best-effort — don't fail if storage unavailable)
    file_ref = ""
    try:
        storage = get_storage()
        file_ref = f"imports/{org.id}/{file_hash}/{filename}"
        storage.upload(file_ref, file_bytes)
    except Exception:
        pass  # Storage is best-effort for local development

    # Build customer lookup map
    customers = {c.name.lower(): str(c.id) for c in Customer.objects.filter(organization=org)}
    # Existing invoice numbers for duplicate detection
    existing_numbers = set(
        Invoice.objects.filter(organization=org, status=Invoice.Status.ISSUED)
        .values_list("invoice_number", flat=True)
    )

    with transaction.atomic():
        batch = ImportBatch.objects.create(
            organization=org,
            batch_type=ImportBatch.BatchType.INVOICE,
            file_name=filename,
            file_hash=file_hash,
            file_reference=file_ref,
            status=ImportBatch.Status.PREVIEW_READY,
            rows_total=len(raw_rows),
            created_by=request.user,
        )
        row_objects = []
        valid_count = error_count = dup_count = 0
        for i, raw in enumerate(raw_rows, start=1):
            result = validate_invoice_row(raw, i, customers)
            row_status = ImportRow.RowStatus.VALID
            if result["errors"]:
                row_status = ImportRow.RowStatus.ERROR
                error_count += 1
            elif result["normalized"].get("invoice_number") in existing_numbers:
                row_status = ImportRow.RowStatus.DUPLICATE
                result["warnings"].append("Invoice number already exists.")
                dup_count += 1
            else:
                valid_count += 1
            row_objects.append(ImportRow(
                batch=batch,
                row_number=i,
                raw_data=raw,
                normalized_data=result["normalized"],
                status=row_status,
                errors=result["errors"],
                warnings=result["warnings"],
            ))
        ImportRow.objects.bulk_create(row_objects)
        batch.rows_valid = valid_count
        batch.rows_rejected = error_count
        batch.rows_flagged = dup_count
        batch.save()

    return Response({
        "batch_id": str(batch.id),
        "status": batch.status,
        "summary": {
            "total": batch.rows_total,
            "valid": batch.rows_valid,
            "errors": batch.rows_rejected,
            "duplicates": batch.rows_flagged,
        },
        "rows": _serialize_rows(row_objects),
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def invoice_batch_detail(request, batch_id):
    """Poll batch status and preview rows."""
    try:
        batch = ImportBatch.objects.get(
            id=batch_id,
            organization=request.membership.organization,
            batch_type=ImportBatch.BatchType.INVOICE,
        )
    except ImportBatch.DoesNotExist:
        return Response({"detail": "Batch not found."}, status=status.HTTP_404_NOT_FOUND)

    rows = ImportRow.objects.filter(batch=batch)
    return Response({
        "batch_id": str(batch.id),
        "status": batch.status,
        "summary": {
            "total": batch.rows_total,
            "valid": batch.rows_valid,
            "created": batch.rows_created,
            "rejected": batch.rows_rejected,
            "skipped": batch.rows_skipped,
            "flagged": batch.rows_flagged,
        },
        "rows": _serialize_rows(rows),
    })


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def invoice_batch_commit(request, batch_id):
    """
    Commit selected valid rows from an import batch as Invoice records.
    Request body: {"row_ids": ["uuid1", "uuid2", ...]}
    """
    org = request.membership.organization
    try:
        batch = ImportBatch.objects.get(
            id=batch_id,
            organization=org,
            batch_type=ImportBatch.BatchType.INVOICE,
        )
    except ImportBatch.DoesNotExist:
        return Response({"detail": "Batch not found."}, status=status.HTTP_404_NOT_FOUND)

    if batch.status == ImportBatch.Status.COMMITTED:
        return Response({"detail": "This batch has already been committed."}, status=status.HTTP_400_BAD_REQUEST)

    selected_ids = request.data.get("row_ids", [])
    if not selected_ids:
        return Response({"detail": "No row IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

    rows = ImportRow.objects.filter(
        batch=batch,
        id__in=selected_ids,
        status=ImportRow.RowStatus.VALID,
    )

    created = 0
    skipped = 0
    errors = []

    with transaction.atomic():
        for row in rows:
            nd = row.normalized_data
            try:
                Invoice.objects.create(
                    organization=org,
                    customer_id=nd["customer_id"],
                    invoice_number=nd["invoice_number"],
                    invoice_date=nd["invoice_date"],
                    due_date=nd["due_date"],
                    currency=nd.get("currency", org.default_currency),
                    subtotal_minor=nd["subtotal_minor"],
                    discount_minor=nd.get("discount_minor", 0),
                    tax_minor=nd.get("tax_minor", 0),
                    total_minor=nd["total_minor"],
                    notes=nd.get("notes", ""),
                    status=Invoice.Status.ISSUED,
                    source=Invoice.Source.IMPORT,
                    created_by=request.user,
                    import_batch=batch,
                )
                row.status = ImportRow.RowStatus.COMMITTED
                row.save()
                created += 1
            except Exception as exc:
                skipped += 1
                errors.append({"row_number": row.row_number, "error": str(exc)})

        batch.rows_created = created
        batch.rows_skipped = skipped
        batch.status = ImportBatch.Status.COMMITTED
        batch.completed_at = timezone.now()
        batch.save()

        AuditLog.objects.create(
            organization=org,
            actor=request.user,
            action="import.committed",
            entity_type="import_batch",
            entity_id=str(batch.id),
            summary=f"Committed invoice import: {created} created, {skipped} skipped",
        )

    return Response({
        "batch_id": str(batch.id),
        "created": created,
        "skipped": skipped,
        "errors": errors,
    })


def _serialize_rows(rows):
    return [
        {
            "id": str(r.id if hasattr(r, "id") else ""),
            "row_number": r.row_number,
            "status": r.status,
            "normalized_data": r.normalized_data,
            "errors": r.errors,
            "warnings": r.warnings,
        }
        for r in rows
    ]
