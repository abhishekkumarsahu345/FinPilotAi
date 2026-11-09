import re
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from .models import (
    Organization, Membership, Customer, Invoice, InvoiceItem,
    Payment, PaymentAllocation, AuditLog,
)

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id", "name", "legal_name", "trading_name", "business_email",
            "contact_phone", "country", "state", "default_currency", "timezone",
            "billing_address", "status", "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def create(self, validated_data):
        from products.gst import create_default_gst_rates
        with transaction.atomic():
            org = Organization.objects.create(**validated_data)
            Membership.objects.create(
                organization=org,
                user=self.context["request"].user,
                role=Membership.Role.OWNER,
            )
            # Seed default GST rates for the new organization.
            create_default_gst_rates(org)
            AuditLog.objects.create(
                organization=org,
                actor=self.context["request"].user,
                action="organization.created",
                entity_type="organization",
                entity_id=str(org.id),
                summary=f"Created organization {org.name}",
            )
            return org


class MembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "user_email", "user_name", "role", "active", "created_at"]
        read_only_fields = ["id", "created_at"]


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id", "name", "contact_name", "email", "phone", "billing_address",
            "gstin", "state", "payment_terms_days", "notes", "active",
            "opt_out", "opt_out_recorded_at", "created_at",
        ]
        read_only_fields = ["id", "opt_out_recorded_at", "created_at"]

    def validate_email(self, value):
        if value:
            # Basic format already enforced by EmailField; just normalise
            return value.lower()
        return value

    def validate_gstin(self, value):
        if value and not GSTIN_RE.match(value.upper()):
            raise serializers.ValidationError(
                "GSTIN must be in the format 22AAAAA0000A1Z5. "
                "This is a format check only, not official government verification."
            )
        return value.upper() if value else value

    def validate(self, data):
        org = self.context["request"].membership.organization
        name = data.get("name", getattr(self.instance, "name", ""))
        email = data.get("email", getattr(self.instance, "email", ""))
        phone = data.get("phone", getattr(self.instance, "phone", ""))
        gstin = data.get("gstin", getattr(self.instance, "gstin", ""))

        qs = Customer.objects.filter(organization=org).exclude(
            pk=self.instance.pk if self.instance else None
        )
        warnings = []
        if gstin and qs.filter(gstin__iexact=gstin).exists():
            warnings.append("A customer with this GSTIN already exists.")
        if email and qs.filter(email__iexact=email).exists():
            warnings.append("A customer with this email already exists.")
        if phone and qs.filter(phone=phone).exists():
            warnings.append("A customer with this phone number already exists.")
        if qs.filter(name__iexact=name).exists():
            warnings.append("A customer with this name already exists.")
        if warnings:
            data["_warnings"] = warnings
        return data

    def create(self, validated_data):
        validated_data.pop("_warnings", None)
        return Customer.objects.create(
            organization=self.context["request"].membership.organization,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("_warnings", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # warnings are only present during create/update responses
        return data


# ---------------------------------------------------------------------------
# InvoiceItem
# ---------------------------------------------------------------------------

class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "id", "product", "description", "quantity", "unit_price_minor",
            "discount_minor", "line_total_minor", "sort_order",
            "gst_rate_bps", "gst_rate_name", "hsn_sac",
            "gst_tax_minor", "gst_cgst_minor", "gst_sgst_minor", "gst_igst_minor",
        ]
        read_only_fields = [
            "id", "line_total_minor",
            "gst_tax_minor", "gst_cgst_minor", "gst_sgst_minor", "gst_igst_minor",
        ]

    def validate(self, data):
        qty = data.get("quantity", 1)
        unit = data.get("unit_price_minor", 0)
        disc = data.get("discount_minor", 0)
        if qty <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be positive."})
        if unit <= 0:
            raise serializers.ValidationError({"unit_price_minor": "Unit price must be positive."})
        if disc < 0:
            raise serializers.ValidationError({"discount_minor": "Discount cannot be negative."})
        import math
        line_total = math.floor(float(qty) * unit) - disc
        if line_total <= 0:
            raise serializers.ValidationError("Line total must be positive after discount.")

        # ── GST (server-computed via the single GST service) ──────────────
        rate_bps = data.get("gst_rate_bps", 0) or 0
        if rate_bps < 0:
            raise serializers.ValidationError({"gst_rate_bps": "GST rate cannot be negative."})
        # Taxable value is the line total after line discount.
        from products.gst import compute_line_tax_minor
        data["line_total_minor"] = line_total
        data["gst_tax_minor"] = compute_line_tax_minor(line_total, rate_bps)
        # The CGST/SGST/IGST split depends on place of supply (invoice-level),
        # so it is set by the parent InvoiceSerializer after validating the
        # customer/organization states.
        data["gst_cgst_minor"] = 0
        data["gst_sgst_minor"] = 0
        data["gst_igst_minor"] = 0
        return data


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

class InvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    paid_minor = serializers.SerializerMethodField()
    balance_minor = serializers.SerializerMethodField()
    display_status = serializers.SerializerMethodField()
    items = InvoiceItemSerializer(many=True, required=False)
    gst_summary = serializers.SerializerMethodField()
    gst_warning = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id", "customer", "customer_name", "invoice_number",
            "invoice_date", "due_date", "currency",
            "subtotal_minor", "discount_minor", "tax_minor", "total_minor",
            "status", "source", "notes",
            "paid_minor", "balance_minor", "display_status",
            "items", "gst_summary", "gst_warning", "created_at",
        ]
        read_only_fields = ["id", "total_minor", "source", "created_at"]
        # subtotal_minor is required for header-only invoices (no items), but is
        # server-computed from line items when `items` are provided. Make it
        # optional at the field level and enforce the presence/positivity rule in
        # validate().
        extra_kwargs = {"subtotal_minor": {"required": False}}

    def get_paid_minor(self, obj):
        return sum(
            a.amount_minor for a in obj.allocations.all() if a.reversed_at is None
        )

    def get_balance_minor(self, obj):
        return max(0, obj.total_minor - self.get_paid_minor(obj))

    def get_display_status(self, obj):
        bal = self.get_balance_minor(obj)
        if obj.status == Invoice.Status.VOID:
            return "void"
        if obj.status == Invoice.Status.DRAFT:
            return "draft"
        if bal == 0:
            return "paid"
        if bal < obj.total_minor:
            return "partially_paid"
        today = timezone.localdate()
        if obj.due_date < today:
            return "overdue"
        return "issued"

    def get_gst_warning(self, obj):
        """Place-of-supply warning stored on the invoice at write time."""
        return getattr(obj, "_gst_warning", "") or ""

    def get_gst_summary(self, obj):
        """Rate-wise GST breakdown, aggregated from stored line snapshots.

        Read-only: this only reads stored values; it never calculates GST.
        If no line carries GST, has_gst is False (the UI hides the GST section).
        """
        from products.gst import rate_label

        items = list(obj.items.all())
        rates = {}
        totals = {
            "taxable_minor": 0,
            "cgst_minor": 0, "sgst_minor": 0, "igst_minor": 0,
            "tax_minor": 0,
        }
        has_gst = False
        for it in items:
            key = it.gst_rate_bps or 0
            g = rates.setdefault(key, {
                "rate_bps": key, "rate_label": rate_label(key) if key else "No GST",
                "taxable_minor": 0, "cgst_minor": 0, "sgst_minor": 0,
                "igst_minor": 0, "tax_minor": 0, "line_count": 0,
            })
            g["taxable_minor"] += it.line_total_minor
            g["cgst_minor"] += it.gst_cgst_minor
            g["sgst_minor"] += it.gst_sgst_minor
            g["igst_minor"] += it.gst_igst_minor
            g["tax_minor"] += it.gst_tax_minor
            g["line_count"] += 1
            totals["taxable_minor"] += it.line_total_minor
            totals["cgst_minor"] += it.gst_cgst_minor
            totals["sgst_minor"] += it.gst_sgst_minor
            totals["igst_minor"] += it.gst_igst_minor
            totals["tax_minor"] += it.gst_tax_minor
            if it.gst_tax_minor > 0:
                has_gst = True

        # Place-of-supply classification
        org_state = obj.organization.state if hasattr(obj.organization, "state") else ""
        cust_state = obj.customer.state if hasattr(obj.customer, "state") else ""
        if not org_state or not cust_state:
            pos = "unknown"
        elif org_state == cust_state:
            pos = "intra_state"
        else:
            pos = "inter_state"

        return {
            "has_gst": has_gst,
            "place_of_supply": pos,
            "warning": self.get_gst_warning(obj),
            "rates": [rates[k] for k in sorted(rates)],
            "totals": {
                **totals,
                "grand_total_minor": obj.total_minor,
            },
        }

    def validate(self, data):
        req = self.context["request"]
        org = req.membership.organization

        customer = data.get("customer", getattr(self.instance, "customer", None))
        if not customer or customer.organization_id != org.id:
            raise serializers.ValidationError(
                {"customer": "Customer must belong to the active organization."}
            )
        currency = data.get("currency", getattr(self.instance, "currency", org.default_currency))
        if currency != org.default_currency:
            raise serializers.ValidationError(
                {"currency": f"Invoice currency must match the organization default ({org.default_currency})."}
            )

        items_data = data.get("items", None)

        # ── Determine place of supply (intra vs inter-state) ─────────────
        from products.gst import determine_place_of_supply, split_line_tax
        is_intra, gst_warning = determine_place_of_supply(org.state or "", customer.state or "")

        # ── Compute totals ───────────────────────────────────────────────
        # When line items are provided, the server computes subtotal and tax
        # from the items (the frontend preview is display-only). When no items
        # are provided (e.g. file import, or a header-only update), the
        # supplied subtotal/tax are used as-is — preserving existing behavior.
        if items_data:
            subtotal = sum(it["line_total_minor"] for it in items_data)
            tax = sum(it.get("gst_tax_minor", 0) for it in items_data)
            data["subtotal_minor"] = subtotal
            data["tax_minor"] = tax
            # Apply the CGST/SGST/IGST split to each line based on place of supply.
            for it in items_data:
                cgst, sgst, igst = split_line_tax(it.get("gst_tax_minor", 0), is_intra)
                it["gst_cgst_minor"] = cgst
                it["gst_sgst_minor"] = sgst
                it["gst_igst_minor"] = igst
        else:
            subtotal = data.get("subtotal_minor", getattr(self.instance, "subtotal_minor", 0))
            discount = data.get("discount_minor", getattr(self.instance, "discount_minor", 0))
            tax = data.get("tax_minor", getattr(self.instance, "tax_minor", 0))

        discount = data.get("discount_minor", getattr(self.instance, "discount_minor", 0))
        if subtotal <= 0:
            raise serializers.ValidationError({"subtotal_minor": "Subtotal must be positive."})
        if discount < 0:
            raise serializers.ValidationError({"discount_minor": "Discount cannot be negative."})
        if tax < 0:
            raise serializers.ValidationError({"tax_minor": "Tax cannot be negative."})
        if discount > subtotal:
            raise serializers.ValidationError(
                {"discount_minor": "Discount cannot exceed subtotal."}
            )

        data["_calculated_total"] = subtotal - discount + tax
        data["_gst_warning"] = gst_warning
        data["_has_items"] = bool(items_data)
        return data

    def create(self, data):
        total = data.pop("_calculated_total")
        gst_warning = data.pop("_gst_warning", "")
        data.pop("_has_items", False)
        items_data = data.pop("items", [])
        req = self.context["request"]
        with transaction.atomic():
            invoice = Invoice.objects.create(
                organization=req.membership.organization,
                created_by=req.user,
                total_minor=total,
                **data,
            )
            invoice._gst_warning = gst_warning
            for idx, item_data in enumerate(items_data):
                item_data["sort_order"] = idx
                InvoiceItem.objects.create(
                    organization=invoice.organization,
                    invoice=invoice,
                    **item_data,
                )
            AuditLog.objects.create(
                organization=invoice.organization,
                actor=req.user,
                action="invoice.created",
                entity_type="invoice",
                entity_id=str(invoice.id),
                summary=f"Created invoice {invoice.invoice_number}",
            )
        return invoice

    def update(self, instance, data):
        total = data.pop("_calculated_total")
        gst_warning = data.pop("_gst_warning", "")
        has_items = data.pop("_has_items", False)
        items_data = data.pop("items", []) if has_items else None
        req = self.context["request"]
        # Guard against changing totals when allocations exist
        active_allocs = instance.allocations.filter(reversed_at__isnull=True)
        if active_allocs.exists() and total != instance.total_minor:
            raise serializers.ValidationError(
                "Reverse existing allocations before changing a paid invoice total."
            )
        if data.get("status") == Invoice.Status.VOID and active_allocs.exists():
            raise serializers.ValidationError(
                "Invoices with active allocations cannot be voided. Reverse allocations first."
            )
        with transaction.atomic():
            for key, value in data.items():
                setattr(instance, key, value)
            instance.total_minor = total
            instance.updated_by = req.user
            instance.save()
            # Replace line items when provided (supports editing GST on an invoice).
            if items_data is not None:
                instance.items.all().delete()
                for idx, item_data in enumerate(items_data):
                    item_data["sort_order"] = idx
                    InvoiceItem.objects.create(
                        organization=instance.organization,
                        invoice=instance,
                        **item_data,
                    )
            instance._gst_warning = gst_warning
            AuditLog.objects.create(
                organization=instance.organization,
                actor=req.user,
                action="invoice.updated",
                entity_type="invoice",
                entity_id=str(instance.id),
                summary=f"Updated invoice {instance.invoice_number}",
            )
        return instance


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

class AllocationInputSerializer(serializers.Serializer):
    invoice = serializers.UUIDField()
    amount_minor = serializers.IntegerField(min_value=1)


class AllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = ["id", "invoice", "invoice_number", "amount_minor", "created_at", "reversed_at"]


class PaymentSerializer(serializers.ModelSerializer):
    allocations_input = AllocationInputSerializer(many=True, write_only=True, required=False)
    allocations = AllocationSerializer(many=True, read_only=True)
    unallocated_minor = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "customer", "payment_date", "amount_minor", "currency",
            "method", "reference", "notes", "status",
            "allocations_input", "allocations", "unallocated_minor", "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def get_unallocated_minor(self, obj):
        allocated = sum(
            a.amount_minor for a in obj.allocations.all() if a.reversed_at is None
        )
        return max(0, obj.amount_minor - allocated)

    def validate(self, data):
        req = self.context["request"]
        org = req.membership.organization
        customer = data.get("customer", getattr(self.instance, "customer", None))

        if customer and customer.organization_id != org.id:
            raise serializers.ValidationError(
                {"customer": "Customer is outside the active organization."}
            )
        amount = data.get("amount_minor", getattr(self.instance, "amount_minor", 0))
        if amount <= 0:
            raise serializers.ValidationError(
                {"amount_minor": "Payment amount must be positive."}
            )
        currency = data.get("currency", getattr(self.instance, "currency", org.default_currency))
        if currency != org.default_currency:
            raise serializers.ValidationError(
                {"currency": f"Payment currency must match the organization default ({org.default_currency})."}
            )

        # Duplicate reference warning (non-blocking)
        ref = data.get("reference", "")
        if ref:
            exists = Payment.objects.filter(
                organization=org, customer=customer, reference=ref
            ).exclude(pk=getattr(self.instance, "pk", None)).exists()
            if exists:
                data["_duplicate_ref_warning"] = (
                    f"A payment with reference '{ref}' already exists for this customer."
                )

        # Idempotency: exact duplicate by key fields
        payment_date = data.get("payment_date")
        if ref and payment_date and customer:
            exact = Payment.objects.filter(
                organization=org,
                customer=customer,
                amount_minor=amount,
                currency=currency,
                payment_date=payment_date,
                reference=ref,
            ).first()
            if exact:
                data["_idempotent_existing"] = exact

        allocations = data.get("allocations_input", [])
        alloc_total = sum(x["amount_minor"] for x in allocations)
        if alloc_total > amount:
            raise serializers.ValidationError(
                f"Total allocation of ₹{alloc_total / 100:,.2f} exceeds "
                f"payment amount of ₹{amount / 100:,.2f}."
            )
        seen_invoices = set()
        for item in allocations:
            if item["invoice"] in seen_invoices:
                raise serializers.ValidationError("Duplicate invoice in allocations.")
            seen_invoices.add(item["invoice"])
            inv = Invoice.objects.filter(
                id=item["invoice"],
                organization=org,
                customer=customer,
                status=Invoice.Status.ISSUED,
            ).prefetch_related("allocations").first()
            if not inv:
                raise serializers.ValidationError(
                    f"Invoice {item['invoice']} must be issued, belong to this "
                    "customer and organization."
                )
            active_paid = sum(
                a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
            )
            if item["amount_minor"] > inv.total_minor - active_paid:
                raise serializers.ValidationError(
                    f"Allocation of ₹{item['amount_minor'] / 100:,.2f} exceeds "
                    f"invoice {inv.invoice_number} outstanding balance of "
                    f"₹{(inv.total_minor - active_paid) / 100:,.2f}."
                )
        return data

    @transaction.atomic
    def create(self, data):
        # Idempotency — return existing payment if exact match
        existing = data.pop("_idempotent_existing", None)
        if existing:
            return existing
        data.pop("_duplicate_ref_warning", None)
        allocations = data.pop("allocations_input", [])
        req = self.context["request"]
        payment = Payment.objects.create(
            organization=req.membership.organization,
            recorded_by=req.user,
            **data,
        )
        for item in allocations:
            inv = Invoice.objects.select_for_update().get(
                id=item["invoice"],
                organization=payment.organization,
            )
            PaymentAllocation.objects.create(
                organization=payment.organization,
                payment=payment,
                invoice=inv,
                amount_minor=item["amount_minor"],
                created_by=req.user,
            )
        AuditLog.objects.create(
            organization=payment.organization,
            actor=req.user,
            action="payment.recorded",
            entity_type="payment",
            entity_id=str(payment.id),
            summary=f"Recorded payment of ₹{payment.amount_minor / 100:.2f}",
        )
        return payment


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

class AuditSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id", "action", "entity_type", "entity_id",
            "summary", "actor_name", "request_id", "created_at",
        ]

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name() or obj.actor.email
        return "System"
