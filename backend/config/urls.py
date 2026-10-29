from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # API v1
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("imports_app.urls")),
    path("api/v1/", include("reminders.urls")),
    path("api/v1/", include("reconciliation.urls")),
    path("api/v1/", include("forecast.urls")),
    path("api/v1/", include("ai_assistant.urls")),
    path("api/v1/", include("notifications.urls")),
    path("api/v1/", include("subscriptions.urls")),
    path("api/v1/", include("exports.urls")),
    path("api/v1/", include("platform_admin.urls")),
]
