from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .acting import clear_acting_user, data_user, set_acting_user
from .permissions import IsMenuAdmin
from .services.accounts import account_row, create_account, delete_account, update_account
from .services.tenant_db import postgres_enabled, provision_tenant

User = get_user_model()


class AccountListView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request):
        users = [
            account_row(user, request.user)
            for user in User.objects.order_by("username")
        ]
        return Response({"users": users, "database_mode": "postgresql" if postgres_enabled() else "sqlite"})

    def post(self, request):
        try:
            user = create_account(
                request.data.get("username"),
                request.data.get("email"),
                request.data.get("password"),
                request.data.get("plan") or "basic",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(account_row(user, request.user), status=status.HTTP_201_CREATED)


class AccountDetailView(APIView):
    permission_classes = [IsMenuAdmin]

    def _user(self, user_id):
        return User.objects.filter(pk=user_id).first()

    def patch(self, request, user_id):
        user = self._user(user_id)
        if user is None:
            return Response({"detail": "Account not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            update_account(user, request.data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(account_row(user, request.user))

    def delete(self, request, user_id):
        user = self._user(user_id)
        if user is None:
            return Response({"detail": "Account not found."}, status=status.HTTP_404_NOT_FOUND)
        if user.id == request.user.id:
            return Response(
                {"detail": "You cannot delete the account you are signed in with."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            delete_account(user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        clear_acting_user(request, user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountProvisionView(APIView):
    permission_classes = [IsMenuAdmin]

    def post(self, request, user_id):
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return Response({"detail": "Account not found."}, status=status.HTTP_404_NOT_FOUND)
        plan = request.data.get("plan") or None
        try:
            provision_tenant(user, plan)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(account_row(user, request.user))


class ActAsView(APIView):
    permission_classes = [IsMenuAdmin]

    def post(self, request):
        raw = request.data.get("user_id")
        if raw in (None, "", 0, "0"):
            set_acting_user(request, None)
            return Response({"acting_as": None})
        try:
            user_id = int(raw)
        except (TypeError, ValueError):
            return Response({"detail": "Choose an account."}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            return Response({"detail": "Account not found."}, status=status.HTTP_404_NOT_FOUND)
        set_acting_user(request, user if user.id != request.user.id else None)
        acting = data_user(request)
        if acting.id == request.user.id:
            return Response({"acting_as": None})
        return Response({"acting_as": account_row(acting, request.user)})
