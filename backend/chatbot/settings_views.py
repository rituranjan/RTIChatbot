from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsMenuAdmin
from .services.admin_settings import purge_expired_data, save_settings, settings_payload


class AdminSettingsView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request):
        return Response(settings_payload(request.user))

    def patch(self, request):
        try:
            payload = save_settings(request.data, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


class AdminPurgeView(APIView):
    permission_classes = [IsMenuAdmin]

    def post(self, request):
        result = purge_expired_data()
        body = settings_payload(request.user)
        body["purge"] = result
        if not result["ran"]:
            return Response(
                {"detail": "Set the number of days above 0 before deleting old data.", **body},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(body)
