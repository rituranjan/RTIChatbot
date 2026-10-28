from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsMenuAdmin
from .services.prompt_service import activate_version, list_prompts, preview_prompt, save_prompt


class AdminPromptListView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request):
        return Response({"prompts": list_prompts()})


class AdminPromptDetailView(APIView):
    permission_classes = [IsMenuAdmin]

    def patch(self, request, slug):
        try:
            rows = save_prompt(slug, request.data, user_id=request.user.pk)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        match = next((row for row in rows if row["slug"] == slug), None)
        return Response({"prompt": match, "prompts": rows})

    def post(self, request, slug):
        """Preview resolved template."""
        try:
            payload = preview_prompt(slug, request.data.get("variables"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


class AdminPromptActivateView(APIView):
    permission_classes = [IsMenuAdmin]

    def post(self, request, slug):
        try:
            version = int(request.data.get("version"))
        except (TypeError, ValueError):
            return Response({"detail": "Enter a version number."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rows = activate_version(slug, version, user_id=request.user.pk)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"prompts": rows})


class AdminLlmUsageView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request):
        from django.db.models import Count, Sum

        from ..models import LlmUsageLog

        recent = list(
            LlmUsageLog.objects.select_related("user")
            .order_by("-created_at")[:50]
            .values(
                "id",
                "created_at",
                "workflow",
                "model",
                "prompt_slug",
                "estimated_input_tokens",
                "actual_input_tokens",
                "actual_output_tokens",
                "cached_tokens",
                "latency_ms",
                "success",
                "user__username",
            )
        )
        totals = LlmUsageLog.objects.aggregate(
            requests=Count("id"),
            input_tokens=Sum("actual_input_tokens"),
            output_tokens=Sum("actual_output_tokens"),
            cached_tokens=Sum("cached_tokens"),
        )
        by_workflow = list(
            LlmUsageLog.objects.values("workflow")
            .annotate(count=Count("id"), input=Sum("actual_input_tokens"))
            .order_by("-count")[:20]
        )
        return Response({"recent": recent, "totals": totals, "by_workflow": by_workflow})
