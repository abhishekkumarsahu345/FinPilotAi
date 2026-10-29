from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status as drf_status

from core.permissions import HasOrganizationAccess
from .services import generate_forecast


VALID_PERIODS = {7, 30, 60}
VALID_ASSUMPTIONS = {"due_date", "historical_delay", "custom_offset"}


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def forecast_view(request):
    """
    GET /api/v1/forecasts/
    Query params:
      - period: 7, 30, or 60 (days)
      - timing: due_date | historical_delay | custom_offset
      - offset: integer day offset (for custom_offset)
    """
    org = request.membership.organization

    period_str = request.query_params.get("period", "30")
    try:
        period = int(period_str)
    except ValueError:
        return Response(
            {"detail": "period must be 7, 30, or 60."},
            status=drf_status.HTTP_400_BAD_REQUEST,
        )
    if period not in VALID_PERIODS:
        return Response(
            {"detail": "period must be one of: 7, 30, 60."},
            status=drf_status.HTTP_400_BAD_REQUEST,
        )

    timing = request.query_params.get("timing", "due_date")
    if timing not in VALID_ASSUMPTIONS:
        return Response(
            {"detail": f"timing must be one of: {', '.join(VALID_ASSUMPTIONS)}."},
            status=drf_status.HTTP_400_BAD_REQUEST,
        )

    offset = 0
    if timing == "custom_offset":
        try:
            offset = int(request.query_params.get("offset", "0"))
        except ValueError:
            return Response({"detail": "offset must be an integer."}, status=400)

    result = generate_forecast(org, period, timing, offset)
    return Response(result)
