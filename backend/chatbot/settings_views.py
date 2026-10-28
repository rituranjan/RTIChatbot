from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .acting import data_user
from .permissions import IsMenuAdmin
from .services.admin_settings import purge_expired_data, save_settings, settings_payload
from .services.llm_service import LLMError
from .services.openrouter_service import list_models
from .services.plan_access import my_plan_payload, set_selected_model


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


class OpenRouterModelsView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request):
        try:
            models = list_models(request.query_params.get("q") or "")
        except LLMError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"models": models})


class MyPlanView(APIView):
    def get(self, request):
        return Response(my_plan_payload(data_user(request)))

    def patch(self, request):
        try:
            payload = set_selected_model(data_user(request), request.data.get("selected_model"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)
