import re
import uuid
from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

class Organization(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    trading_name = models.CharField(max_length=255, blank=True)
    business_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=2, default="IN")
    default_currency = models.CharField(max_length=3, default="INR")
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    billing_address = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------

class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Business Owner"
        MANAGER = "manager", "Finance Manager"
        ACCOUNTANT = "accountant", "Accountant"
        COLLECTOR = "collector", "Collections Executive"
        VIEWER = "viewer", "Viewer"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="unique_org_member"
            )
        ]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

GSTIN_PATTERN = re.compile(
    r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="customers"
    )
    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    billing_address = models.TextField(blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    payment_terms_days = models.PositiveSmallIntegerField(default=30)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    # Reminder opt-out
    opt_out = models.BooleanField(default=False)
    opt_out_recorded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["organization", "name"]),
            models.Index(fields=["organization", "active"]),
        ]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        VOID = "void", "Void"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual entry"
        IMPORT = "import", "File import"
        EXTRACTION = "extraction", "AI extraction"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invoices"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="invoices"
    )
    invoice_number = models.CharField(max_length=64)
    invoice_date = models.DateField()
    due_date = models.DateField()
    currency = models.CharField(max_length=3, default="INR")
    subtotal_minor = models.BigIntegerField()
    discount_minor = models.BigIntegerField(default=0)
    tax_minor = models.BigIntegerField(default=0)
    total_minor = models.BigIntegerField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    source = models.CharField(
        max_length=16, choices=Source.choices, default=Source.MANUAL
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_invoices",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="updated_invoices",
    )
    import_batch = models.ForeignKey(
        "imports_app.ImportBatch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ["-invoice_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "invoice_number"],
                name="unique_invoice_number_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal_minor__gt=0),
                name="invoice_subtotal_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_minor__gte=0),
                name="invoice_discount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_minor__gte=0),
                name="invoice_tax_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(total_minor__gt=0),
                name="invoice_total_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "due_date", "status"]),
            models.Index(fields=["organization", "customer", "status"]),
        ]

    def __str__(self):
        return f"{self.invoice_number} ({self.organization})"


# ---------------------------------------------------------------------------
# InvoiceItem
# ---------------------------------------------------------------------------

class InvoiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invoice_items"
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="items"
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1)
    unit_price_minor = models.BigIntegerField()
    discount_minor = models.BigIntegerField(default=0)
    # line_total_minor = (quantity * unit_price_minor) - discount_minor, server-calculated
    line_total_minor = models.BigIntegerField()
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(unit_price_minor__gt=0),
                name="item_unit_price_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(line_total_minor__gt=0),
                name="item_line_total_positive",
            ),
        ]

    def __str__(self):
        return f"{self.description} × {self.quantity}"


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

class Payment(models.Model):
    class Method(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        UPI = "upi", "UPI"
        CHEQUE = "cheque", "Cheque"
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVERSED = "reversed", "Reversed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="payments"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="payments"
    )
    payment_date = models.DateField()
    amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    method = models.CharField(
        max_length=24, choices=Method.choices, default=Method.BANK_TRANSFER
    )
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    idempotency_key = models.CharField(max_length=128, blank=True, db_index=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_payments"
    )
    source = models.CharField(max_length=24, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0),
                name="payment_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "customer", "payment_date"]),
            models.Index(fields=["organization", "reference"]),
        ]

    def __str__(self):
        return f"Payment {self.id} — {self.amount_minor} paise"


# ---------------------------------------------------------------------------
# PaymentAllocation
# ---------------------------------------------------------------------------

class PaymentAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="payment_allocations"
    )
    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, related_name="allocations"
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name="allocations"
    )
    amount_minor = models.BigIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_allocations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Reversal tracking — original allocation is never deleted
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_allocations",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0),
                name="allocation_amount_positive",
            ),
        ]

    def is_active(self):
        return self.reversed_at is None

    def __str__(self):
        return f"Alloc {self.id}"


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    action = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=80, blank=True)
    summary = models.CharField(max_length=500)
    request_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self):
        return f"{self.action} on {self.entity_type} {self.entity_id}"
