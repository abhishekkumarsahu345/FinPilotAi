import uuid
from django.conf import settings
from django.db import models

from core.models import Organization


class GSTRate(models.Model):
    """
    An organization's own GST rate. The user enters only the total rate;
    CGST/SGST are equal halves and IGST is the full rate (computed at invoice
    time based on place of supply). Stored as integer basis points
    (100 bps = 1%, so 1800 = 18%).

    A rate that has been used on an invoice can be deactivated but never
    deleted, so historical invoices stay valid (they also snapshot the value).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="gst_rates"
    )
    name = models.CharField(max_length=64)
    rate_bps = models.IntegerField()  # basis points; 1800 = 18%
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ["rate_bps"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rate_bps__gte=0), name="gst_rate_nonnegative"
            ),
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_gst_rate_name_per_org"
            ),
        ]
        indexes = [models.Index(fields=["organization", "active"])]

    def __str__(self):
        return f"{self.name} ({self.rate_bps / 100:g}%)"


class Product(models.Model):
    """A sellable item. Price is paise. The default GST rate is optional —
    "No GST" is a valid choice; the real GST decision happens on the invoice line."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=32, default="Nos")
    sku = models.CharField(max_length=64, blank=True)
    hsn_sac = models.CharField(max_length=16, blank=True)
    price_minor = models.BigIntegerField()  # paise
    default_gst_rate = models.ForeignKey(
        GSTRate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="products",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price_minor__gt=0), name="product_price_positive"
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "name"]),
            models.Index(fields=["organization", "active"]),
            models.Index(fields=["organization", "sku"]),
        ]

    def __str__(self):
        return self.name
