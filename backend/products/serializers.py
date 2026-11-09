from django.db import transaction
from rest_framework import serializers

from core.models import AuditLog
from .models import Product, GSTRate
from .gst import rate_label


# ---------------------------------------------------------------------------
# GSTRate
# ---------------------------------------------------------------------------

class GSTRateSerializer(serializers.ModelSerializer):
    # Read-only convenience splits for preview/display.
    rate_percent = serializers.SerializerMethodField()
    cgst_percent = serializers.SerializerMethodField()
    sgst_percent = serializers.SerializerMethodField()
    igst_percent = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()
    in_use = serializers.SerializerMethodField()

    class Meta:
        model = GSTRate
        fields = [
            "id", "name", "rate_bps", "active",
            "rate_percent", "cgst_percent", "sgst_percent", "igst_percent",
            "preview", "in_use", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def _pct(self, bps):
        from decimal import Decimal
        if bps is None or bps <= 0:
            return "0%"
        return f"{(Decimal(bps) / Decimal(100)).normalize():g}%"

    def get_rate_percent(self, obj):
        return self._pct(obj.rate_bps)

    def get_cgst_percent(self, obj):
        return self._pct(obj.rate_bps // 2 if obj.rate_bps else 0)

    def get_sgst_percent(self, obj):
        return self._pct(obj.rate_bps // 2 if obj.rate_bps else 0)

    def get_igst_percent(self, obj):
        return self._pct(obj.rate_bps)

    def get_preview(self, obj):
        if not obj.rate_bps:
            return "No GST"
        half = obj.rate_bps // 2
        return f"CGST {self._pct(half)} + SGST {self._pct(half)} | IGST {self._pct(obj.rate_bps)}"

    def get_in_use(self, obj):
        """True if this rate has been applied to any invoice line (snapshot)."""
        from core.models import InvoiceItem
        return InvoiceItem.objects.filter(
            organization=obj.organization, gst_rate_bps=obj.rate_bps
        ).exists()

    def validate_rate_bps(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError("GST rate must be zero or positive (basis points).")
        return value

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def validate(self, data):
        org = self.context["request"].membership.organization
        name = data.get("name", getattr(self.instance, "name", ""))
        qs = GSTRate.objects.filter(organization=org, name__iexact=name).exclude(
            pk=getattr(self.instance, "pk", None)
        )
        if qs.exists():
            raise serializers.ValidationError(
                {"name": "A GST rate with this name already exists."}
            )
        return data

    def create(self, validated_data):
        req = self.context["request"]
        with transaction.atomic():
            rate = GSTRate.objects.create(
                organization=req.membership.organization, **validated_data
            )
            AuditLog.objects.create(
                organization=rate.organization, actor=req.user,
                action="gst_rate.created", entity_type="gst_rate",
                entity_id=str(rate.id),
                summary=f"Created GST rate {rate.name} ({rate_label(rate.rate_bps)})",
            )
        return rate

    def update(self, instance, validated_data):
        req = self.context["request"]
        with transaction.atomic():
            for key, value in validated_data.items():
                setattr(instance, key, value)
            instance.save()
            AuditLog.objects.create(
                organization=instance.organization, actor=req.user,
                action="gst_rate.updated", entity_type="gst_rate",
                entity_id=str(instance.id),
                summary=f"Updated GST rate {instance.name}",
            )
        return instance


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class ProductSerializer(serializers.ModelSerializer):
    default_gst_rate_bps = serializers.IntegerField(
        source="default_gst_rate.rate_bps", read_only=True, default=0
    )
    default_gst_rate_name = serializers.CharField(
        source="default_gst_rate.name", read_only=True, default=""
    )
    default_gst_rate_preview = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "description", "unit", "sku", "hsn_sac",
            "price_minor", "default_gst_rate", "default_gst_rate_bps",
            "default_gst_rate_name", "default_gst_rate_preview",
            "active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_default_gst_rate_preview(self, obj):
        if obj.default_gst_rate_id and obj.default_gst_rate:
            return rate_label(obj.default_gst_rate.rate_bps)
        return "No GST"

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def validate_price_minor(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Price must be positive (paise).")
        return value

    def validate(self, data):
        org = self.context["request"].membership.organization
        # default_gst_rate must belong to the same org (and be active ideally)
        rate = data.get("default_gst_rate", getattr(self.instance, "default_gst_rate", None))
        if rate and rate.organization_id != org.id:
            raise serializers.ValidationError(
                {"default_gst_rate": "GST rate must belong to the active organization."}
            )
        # Optional non-blocking duplicate-name warning (mirrors Customer pattern)
        name = data.get("name", getattr(self.instance, "name", ""))
        qs = Product.objects.filter(organization=org, name__iexact=name).exclude(
            pk=getattr(self.instance, "pk", None)
        )
        warnings = []
        if qs.exists():
            warnings.append("A product with this name already exists.")
        if warnings:
            data["_warnings"] = warnings
        return data

    def create(self, validated_data):
        validated_data.pop("_warnings", None)
        req = self.context["request"]
        with transaction.atomic():
            product = Product.objects.create(
                organization=req.membership.organization, **validated_data
            )
            AuditLog.objects.create(
                organization=product.organization, actor=req.user,
                action="product.created", entity_type="product",
                entity_id=str(product.id),
                summary=f"Created product {product.name}",
            )
        return product

    def update(self, instance, validated_data):
        validated_data.pop("_warnings", None)
        req = self.context["request"]
        with transaction.atomic():
            for key, value in validated_data.items():
                setattr(instance, key, value)
            instance.save()
            AuditLog.objects.create(
                organization=instance.organization, actor=req.user,
                action="product.updated", entity_type="product",
                entity_id=str(instance.id),
                summary=f"Updated product {instance.name}",
            )
        return instance
