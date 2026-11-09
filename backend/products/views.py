from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import AuditLog
from core.views import OrgScopedMixin
from .models import Product, GSTRate
from .serializers import ProductSerializer, GSTRateSerializer


class GSTRateViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    serializer_class = GSTRateSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    search_fields = ["name"]
    ordering_fields = ["rate_bps", "name", "created_at"]
    filterset_fields = {"active": ["exact"]}

    def get_queryset(self):
        return GSTRate.objects.filter(organization=self.get_org())

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        rate = self.get_object()
        if not rate.active:
            return Response({"detail": "GST rate is already inactive."})
        with transaction.atomic():
            rate.active = False
            rate.save()
            AuditLog.objects.create(
                organization=rate.organization, actor=request.user,
                action="gst_rate.deactivated", entity_type="gst_rate",
                entity_id=str(rate.id),
                summary=f"Deactivated GST rate {rate.name}",
            )
        return Response(GSTRateSerializer(rate, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        rate = self.get_object()
        if rate.active:
            return Response({"detail": "GST rate is already active."})
        with transaction.atomic():
            rate.active = True
            rate.save()
            AuditLog.objects.create(
                organization=rate.organization, actor=request.user,
                action="gst_rate.activated", entity_type="gst_rate",
                entity_id=str(rate.id),
                summary=f"Activated GST rate {rate.name}",
            )
        return Response(GSTRateSerializer(rate, context={"request": request}).data)


class ProductViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    search_fields = ["name", "sku", "hsn_sac"]
    ordering_fields = ["name", "price_minor", "created_at"]
    filterset_fields = {"active": ["exact"]}

    def get_queryset(self):
        return (
            Product.objects.filter(organization=self.get_org())
            .select_related("default_gst_rate")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        warnings = serializer.validated_data.pop("_warnings", [])
        self.perform_create(serializer)
        data = serializer.data
        if warnings:
            data["warnings"] = warnings
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        product = self.get_object()
        if not product.active:
            return Response({"detail": "Product is already inactive."})
        with transaction.atomic():
            product.active = False
            product.save()
            AuditLog.objects.create(
                organization=product.organization, actor=request.user,
                action="product.deactivated", entity_type="product",
                entity_id=str(product.id),
                summary=f"Deactivated product {product.name}",
            )
        return Response(ProductSerializer(product, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        product = self.get_object()
        if product.active:
            return Response({"detail": "Product is already active."})
        with transaction.atomic():
            product.active = True
            product.save()
            AuditLog.objects.create(
                organization=product.organization, actor=request.user,
                action="product.activated", entity_type="product",
                entity_id=str(product.id),
                summary=f"Activated product {product.name}",
            )
        return Response(ProductSerializer(product, context={"request": request}).data)
