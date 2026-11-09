from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import GSTRateViewSet, ProductViewSet

router = DefaultRouter()
router.register("gst-rates", GSTRateViewSet, basename="gst-rates")
router.register("products", ProductViewSet, basename="products")

urlpatterns = [
    path("", include(router.urls)),
]
