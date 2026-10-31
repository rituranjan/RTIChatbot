import re

from django.db import IntegrityError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiTypes, extend_schema

from .models import Conversation, EmbedBot
from .serializers import (
    EmbedChatBodySerializer,
    EmbedProfileBodySerializer,
    EmbedUpdateSerializer,
    MessageSerializer,
)
from .acting import data_user
from .permissions import IsMenuAdmin
from .services.tenant_db import use_tenant
from .services.chat_service import generate_reply
from .services.llm_service import LLMError
from .services.profile_service import profile_answers, public_questions, save_profile
from .services.embed_concurrency import admit_embed_visitor
from .services.embed_domains import verify_embed_parent
from .services.languages import language_public_payload

_VISITOR = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _embed_conversation(bot, visitor: str) -> Conversation:
    """One private thread per (bot, visitor_id). Safe under concurrent embed users."""
    try:
        conversation, _created = Conversation.objects.get_or_create(
            embed_bot=bot,
            visitor_id=visitor,
            defaults={
                "owner_id": bot.owner_id,
                "title": f"Widget · {bot.name}"[:200],
            },
        )
        return conversation
    except IntegrityError:
        conversation = Conversation.objects.filter(embed_bot=bot, visitor_id=visitor).first()
        if conversation:
            return conversation
        raise
    except Exception:
        conversation = Conversation.objects.filter(embed_bot=bot, visitor_id=visitor).first()
        if conversation:
            return conversation
        raise


def ensure_embed_bot(user):
    bot = EmbedBot.objects.filter(owner=user).order_by("created_at").first()
    if bot:
        return bot
    return EmbedBot.objects.create(
        owner=user,
        name="Assistant",
        greeting="Hello! I can help you with documents and account details.",
        quick_replies=["Office hours", "Acme Corp balance"],
    )


def _bot_or_404(bot_id):
    return EmbedBot.objects.filter(id=bot_id, enabled=True).first()


def _public_bot(bot):
    replies = bot.quick_replies if isinstance(bot.quick_replies, list) else []
    return {
        "id": str(bot.id),
        "name": bot.name,
        "greeting": bot.greeting,
        "quick_replies": [str(item) for item in replies if str(item).strip()][:6],
        "accent": bot.accent or "#2563eb",
    }


@method_decorator(csrf_exempt, name="dispatch")
class EmbedConfigView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, bot_id):
        bot = _bot_or_404(bot_id)
        if not bot:
            return Response({"detail": "Chatbot not found."}, status=status.HTTP_404_NOT_FOUND)
        ok, msg = verify_embed_parent(bot.owner, request)
        if not ok:
            return Response({"detail": msg}, status=status.HTTP_403_FORBIDDEN)
        payload = _public_bot(bot)
        payload["language"] = language_public_payload(bot.owner)
        payload["questions"] = public_questions(bot.owner)
        visitor = (request.query_params.get("visitor_id") or "").strip()
        payload["messages"] = []
        payload["profile"] = None
        if _VISITOR.match(visitor):
            allowed, busy = admit_embed_visitor(bot.owner, visitor, embed_bot=bot)
            if not allowed:
                return Response({"detail": busy}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            with use_tenant(bot.owner):
                conversation = Conversation.objects.filter(
                    embed_bot=bot, visitor_id=visitor
                ).first()
                if conversation:
                    payload["messages"] = MessageSerializer(
                        conversation.messages.all(), many=True
                    ).data
                    payload["profile"] = profile_answers(conversation)
        return Response(payload)


@method_decorator(csrf_exempt, name="dispatch")
class EmbedChatView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=EmbedChatBodySerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, bot_id):
        bot = _bot_or_404(bot_id)
        if not bot:
            return Response({"detail": "Chatbot not found."}, status=status.HTTP_404_NOT_FOUND)

        ok, msg = verify_embed_parent(bot.owner, request)
        if not ok:
            return Response({"detail": msg}, status=status.HTTP_403_FORBIDDEN)

        visitor = str(request.data.get("visitor_id") or "").strip()
        user_text = str(request.data.get("message") or "").strip()
        if not _VISITOR.match(visitor):
            return Response({"detail": "Invalid visitor."}, status=status.HTTP_400_BAD_REQUEST)

        allowed, busy = admit_embed_visitor(bot.owner, visitor, embed_bot=bot)
        if not allowed:
            return Response({"detail": busy}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        if not user_text:
            return Response({"detail": "Empty message."}, status=status.HTTP_400_BAD_REQUEST)
        if len(user_text) > 4000:
            return Response({"detail": "Message is too long."}, status=status.HTTP_400_BAD_REQUEST)

        chat_language = str(request.data.get("language") or "").strip() or None

        with use_tenant(bot.owner):
            conversation = Conversation.objects.filter(embed_bot=bot, visitor_id=visitor).first()
            if conversation is None:
                conversation = Conversation.objects.create(
                    owner=bot.owner,
                    embed_bot=bot,
                    visitor_id=visitor,
                    title=f"Widget · {bot.name}"[:200],
                )

            try:
                msg = generate_reply(
                    bot.owner, conversation, user_text, style="widget", chat_language=chat_language
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except LLMError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

            return Response({"message": MessageSerializer(msg).data})


@method_decorator(csrf_exempt, name="dispatch")
class EmbedProfileView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=EmbedProfileBodySerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, bot_id):
        bot = _bot_or_404(bot_id)
        if not bot:
            return Response({"detail": "Chatbot not found."}, status=status.HTTP_404_NOT_FOUND)

        ok, msg = verify_embed_parent(bot.owner, request)
        if not ok:
            return Response({"detail": msg}, status=status.HTTP_403_FORBIDDEN)

        visitor = str(request.data.get("visitor_id") or "").strip()
        if not _VISITOR.match(visitor):
            return Response({"detail": "Invalid visitor."}, status=status.HTTP_400_BAD_REQUEST)

        allowed, busy = admit_embed_visitor(bot.owner, visitor, embed_bot=bot)
        if not allowed:
            return Response({"detail": busy}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        with use_tenant(bot.owner):
            conversation = _embed_conversation(bot, visitor)
            try:
                answers = save_profile(conversation, request.data.get("answers"))
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"profile": answers})


class MyEmbedBotView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request):
        bot = ensure_embed_bot(data_user(request))
        return Response(_owner_payload(bot))

    @extend_schema(request=EmbedUpdateSerializer, responses={200: OpenApiTypes.OBJECT})
    def patch(self, request):
        bot = ensure_embed_bot(data_user(request))
        name = str(request.data.get("name") or "").strip()
        greeting = str(request.data.get("greeting") or "").strip()
        accent = str(request.data.get("accent") or "").strip()
        replies = request.data.get("quick_replies")
        if name:
            bot.name = name[:80]
        if greeting:
            bot.greeting = greeting[:1000]
        if accent.startswith("#") and len(accent) in (4, 7):
            bot.accent = accent
        if isinstance(replies, list):
            bot.quick_replies = [str(item).strip()[:80] for item in replies if str(item).strip()][:6]
        bot.save()
        return Response(_owner_payload(bot))


def _owner_payload(bot):
    data = _public_bot(bot)
    data["enabled"] = bot.enabled
    return data
