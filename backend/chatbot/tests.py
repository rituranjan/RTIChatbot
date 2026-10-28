from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AppSetting, Conversation, Document, Message, MonthlyUsage, UserChatSetting, UserProfile, WebSource
from .services.admin_settings import not_found_reply, purge_expired_data
from .services.web_html import html_to_text, links_from_html
from .services.web_urls import WebUrlError, assert_public_host, normalize_url, site_key

User = get_user_model()


class CrossUserIsolationTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="alicepass123")
        self.bob = User.objects.create_user("bob", password="bobpass123")

        self.alice_conv = Conversation.objects.create(owner=self.alice, title="Alice chat")
        self.bob_conv = Conversation.objects.create(owner=self.bob, title="Bob chat")
        Message.objects.create(
            conversation=self.alice_conv, role="user", content="Alice secret"
        )

        self.alice_doc = Document.objects.create(
            owner=self.alice, title="Alice doc", status=Document.STATUS_READY
        )
        self.bob_doc = Document.objects.create(
            owner=self.bob, title="Bob doc", status=Document.STATUS_READY
        )

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_conversation_list_is_isolated(self):
        r = self._client(self.alice).get("/api/conversations/")
        self.assertEqual(r.status_code, 200)
        ids = [str(x["id"]) for x in r.json()["results"]]
        self.assertIn(str(self.alice_conv.id), ids)
        self.assertNotIn(str(self.bob_conv.id), ids)

    def test_cannot_retrieve_other_conversation(self):
        r = self._client(self.bob).get(f"/api/conversations/{self.alice_conv.id}/")
        self.assertEqual(r.status_code, 404)

    def test_cannot_delete_other_conversation(self):
        r = self._client(self.bob).delete(f"/api/conversations/{self.alice_conv.id}/")
        self.assertEqual(r.status_code, 404)

    def test_cannot_delete_other_document(self):
        r = self._client(self.bob).delete(f"/api/documents/{self.alice_doc.id}/")
        self.assertEqual(r.status_code, 403)

    def test_document_list_is_isolated(self):
        r = self._client(self.alice).get("/api/documents/")
        self.assertEqual(r.status_code, 403)

    def test_retrieval_filters_by_owner(self):
        from .services.retrieval_service import accessible_documents

        ids = set(str(d.id) for d in accessible_documents(self.alice))
        self.assertIn(str(self.alice_doc.id), ids)
        self.assertNotIn(str(self.bob_doc.id), ids)


class SystemEndpointsTests(TestCase):
    def test_health_endpoint_is_public(self):
        r = APIClient().get("/api/system/health/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok"})

    def test_ollama_status_requires_auth(self):
        r = APIClient().get("/api/system/ollama/")
        self.assertIn(r.status_code, (401, 403))


class WebsiteUrlTests(SimpleTestCase):
    def test_normalizes_a_public_site(self):
        self.assertEqual(normalize_url("https://rtiguru.com/"), "https://rtiguru.com/")
        self.assertEqual(normalize_url("https://www.RTIGuru.com/about/"), "https://www.rtiguru.com/about")
        self.assertEqual(site_key("www.rtiguru.com"), "rtiguru.com")

    def test_links_stay_on_the_same_site(self):
        html = (
            '<a href="/pricing">Price</a>'
            '<a href="https://example.com/other">Out</a>'
            '<a href="/logo.png">Logo</a>'
        )
        self.assertEqual(
            links_from_html(html, "https://rtiguru.com/", "rtiguru.com"),
            ["https://rtiguru.com/pricing"],
        )

    def test_page_text_skips_menus_and_scripts(self):
        html = (
            "<html><head><title>About</title><script>secret()</script></head>"
            "<body><nav>Menu</nav><main>Right to information help.</main></body></html>"
        )
        title, text = html_to_text(html)
        self.assertEqual(title, "About")
        self.assertIn("Right to information", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("Menu", text)

    def test_private_hosts_are_rejected(self):
        with self.assertRaises(WebUrlError):
            assert_public_host("127.0.0.1")
        with self.assertRaises(WebUrlError):
            assert_public_host("localhost")


class WebsiteAdminTests(TestCase):
    def test_only_the_menu_admin_can_add_a_website(self):
        user = User.objects.create_user("alice", password="alicepass123")
        response = APIClient()
        response.force_authenticate(user=user)
        denied = response.post("/api/websites/", {"url": "https://rtiguru.com/"}, format="json")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(WebSource.objects.count(), 0)

    def test_private_url_is_rejected_before_a_crawl(self):
        admin = User.objects.create_user("RRGupta", password="password123")
        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.post("/api/websites/", {"url": "http://127.0.0.1/secret"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(WebSource.objects.count(), 0)


class AdminSettingsTests(TestCase):
    def test_old_chats_and_files_are_deleted_for_every_user(self):
        alice = User.objects.create_user("alice2", password="alicepass123")
        bob = User.objects.create_user("bob2", password="bobpass123")
        AppSetting.objects.create(pk=1, retention_days=7, not_found_message="Nothing matched.")
        old = Conversation.objects.create(owner=alice, title="Old")
        recent = Conversation.objects.create(owner=bob, title="New")
        past = timezone.now() - timedelta(days=10)
        Conversation.objects.filter(pk=old.pk).update(updated_at=past, created_at=past)
        old_file = Document.objects.create(owner=alice, title="Old file", status=Document.STATUS_READY)
        Document.objects.filter(pk=old_file.pk).update(created_at=past)
        Document.objects.create(owner=bob, title="New file", status=Document.STATUS_READY)

        result = purge_expired_data()

        self.assertTrue(result["ran"])
        self.assertEqual(result["conversations"], 1)
        self.assertEqual(result["documents"], 1)
        self.assertFalse(Conversation.objects.filter(pk=old.pk).exists())
        self.assertTrue(Conversation.objects.filter(pk=recent.pk).exists())
        self.assertFalse(Document.objects.filter(title="Old file").exists())
        self.assertTrue(Document.objects.filter(title="New file").exists())

    def test_zero_days_does_not_delete(self):
        user = User.objects.create_user("cara", password="carapass123")
        AppSetting.objects.create(pk=1, retention_days=0)
        Conversation.objects.create(owner=user, title="Keep")
        self.assertFalse(purge_expired_data()["ran"])
        self.assertEqual(Conversation.objects.count(), 1)

    def test_user_sentence_overrides_the_default(self):
        user = User.objects.create_user("dev", password="devpass1234")
        AppSetting.objects.create(pk=1, not_found_message="Ask the office.")
        self.assertEqual(not_found_reply(user), "Ask the office.")
        UserChatSetting.objects.create(user=user, not_found_message="No record for this account.")
        self.assertEqual(not_found_reply(user), "No record for this account.")

    def test_settings_are_admin_only(self):
        user = User.objects.create_user("erin", password="erinpass123")
        client = APIClient()
        client.force_authenticate(user=user)
        self.assertEqual(client.get("/api/admin-settings/").status_code, 403)


class AccountWorkspaceTests(TestCase):
    def tearDown(self):
        from .models import UserProfile
        from .services.tenant_db import drop_tenant

        for profile in UserProfile.objects.all():
            drop_tenant(profile)

    def test_each_account_gets_its_own_database(self):
        from .services.tenant_db import provision_tenant, register_database, sqlite_file, use_tenant

        alice = User.objects.create_user("alice", password="alicepass123")
        bob = User.objects.create_user("bob", password="bobpass123")
        alice_profile = provision_tenant(alice, "gold")
        bob_profile = provision_tenant(bob, "basic")
        self.assertTrue(alice_profile.ready, alice_profile.error)
        self.assertTrue(bob_profile.ready)
        self.assertNotEqual(alice_profile.database_name, bob_profile.database_name)
        self.assertTrue(sqlite_file(alice_profile).exists())
        self.assertTrue(sqlite_file(bob_profile).exists())

        with use_tenant(alice):
            Conversation.objects.create(owner=alice, title="Alice only")
        with use_tenant(bob):
            self.assertFalse(Conversation.objects.filter(title="Alice only").exists())
        self.assertFalse(Conversation.objects.using("default").filter(title="Alice only").exists())
        self.assertTrue(
            Conversation.objects.using(register_database(alice_profile)).filter(title="Alice only").exists()
        )

    def test_plan_schedule_deletes_only_that_plan(self):
        from .services.tenant_db import provision_tenant

        alice = User.objects.create_user("alice4", password="alicepass123")
        bob = User.objects.create_user("bob4", password="bobpass123")
        provision_tenant(alice, "basic")
        provision_tenant(bob, "diamond")
        AppSetting.objects.create(
            pk=1,
            retention_days=0,
            plan_days={"basic": 5, "silver": 0, "gold": 0, "diamond": 0},
            not_found_message="Nothing matched.",
        )
        old = Conversation.objects.create(owner=alice, title="Basic old")
        kept = Conversation.objects.create(owner=bob, title="Diamond kept")
        past = timezone.now() - timedelta(days=10)
        Conversation.objects.filter(pk__in=[old.pk, kept.pk]).update(updated_at=past)

        result = purge_expired_data()

        self.assertTrue(result["ran"])
        self.assertFalse(Conversation.objects.filter(title="Basic old").exists())
        self.assertTrue(Conversation.objects.filter(title="Diamond kept").exists())

    def test_admin_can_manage_accounts_and_work_as_one(self):
        User.objects.create_user("RRGupta", password="password123")
        client = APIClient()
        client.login(username="RRGupta", password="password123")
        created = client.post(
            "/api/admin/accounts/",
            {"username": "mina", "email": "mina@example.com", "password": "minapass123", "plan": "silver"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["plan"], "silver")
        self.assertTrue(created.json()["database_ready"])
        user_id = created.json()["id"]

        switched = client.post("/api/admin/act-as/", {"user_id": user_id}, format="json")
        self.assertEqual(switched.status_code, 200)
        chat = client.post("/api/conversations/", {"title": "Mina chat"}, format="json")
        self.assertEqual(chat.status_code, 201)
        self.assertFalse(Conversation.objects.using("default").filter(title="Mina chat").exists())

        outsider = APIClient()
        outsider.force_authenticate(user=User.objects.create_user("omar", password="omarpass123"))
        self.assertEqual(outsider.get("/api/admin/accounts/").status_code, 403)
        self.assertNotIn(
            str(chat.json()["id"]),
            [row["id"] for row in outsider.get("/api/conversations/").json()["results"]],
        )

        removed = client.delete(f"/api/admin/accounts/{user_id}/")
        self.assertEqual(removed.status_code, 204)
        self.assertFalse(User.objects.filter(username="mina").exists())


class PlanLimitTests(TestCase):
    def _access(self, **overrides):
        basic = {
            "days": 0,
            "models": ["openai/gpt-4o", "openai/gpt-4o-mini"],
            "monthly_requests": 1,
            "input_tokens": 10,
            "output_tokens": 0,
            "cached_tokens": 0,
            "limit_message": "Basic limit reached.",
        }
        basic.update(overrides)
        return {
            "basic": basic,
            "silver": {**basic, "monthly_requests": 20, "limit_message": "Silver limit reached."},
            "gold": {**basic, "monthly_requests": 30, "limit_message": "Gold limit reached."},
            "diamond": {**basic, "monthly_requests": 40, "limit_message": "Diamond limit reached."},
        }

    def test_request_limit_blocks_and_user_can_only_pick_plan_models(self):
        from unittest.mock import patch

        from .services.plan_access import limit_reply, record_usage

        user = User.objects.create_user("lee", email="lee@example.com", password="leepass123")
        AppSetting.objects.update_or_create(
            pk=1, defaults={"plan_access": self._access(), "not_found_message": "Missing."}
        )
        client = APIClient()
        client.force_authenticate(user=user)
        denied = client.patch("/api/my-plan/", {"selected_model": "other/model"}, format="json")
        self.assertEqual(denied.status_code, 400)
        saved = client.patch("/api/my-plan/", {"selected_model": "openai/gpt-4o-mini"}, format="json")
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["selected_model"], "openai/gpt-4o-mini")

        self.assertEqual(limit_reply(user), "")
        record_usage(user, {"input_tokens": 3, "output_tokens": 1, "cached_tokens": 0})
        with patch("chatbot.services.plan_access.send_limit_email", return_value=True) as mailer:
            self.assertEqual(limit_reply(user), "Basic limit reached.")
            mailer.assert_called_once()
            self.assertEqual(limit_reply(user), "Basic limit reached.")
            mailer.assert_called_once()
        usage = MonthlyUsage.objects.get(user=user)
        self.assertEqual(usage.requests, 1)
        self.assertTrue(usage.email_sent)

    def test_zero_token_limit_does_not_block(self):
        from .services.plan_access import limit_reply, record_usage

        user = User.objects.create_user("noor", password="noorpass123")
        AppSetting.objects.update_or_create(
            pk=1,
            defaults={
                "plan_access": self._access(monthly_requests=0, input_tokens=0),
                "not_found_message": "Missing.",
            },
        )
        for _ in range(20):
            record_usage(user, {"input_tokens": 500, "output_tokens": 500, "cached_tokens": 100})
        self.assertEqual(limit_reply(user), "")

    def test_per_request_input_cap_blocks_oversized_request(self):
        from .services.plan_access import projected_limit_block

        user = User.objects.create_user("big", password="bigpass123")
        AppSetting.objects.update_or_create(
            pk=1,
            defaults={"plan_access": self._access(input_tokens=50, monthly_requests=0), "not_found_message": "Missing."},
        )
        self.assertEqual(projected_limit_block(user, 80), "Basic limit reached.")
        self.assertEqual(projected_limit_block(user, 40), "")

    def test_monthly_token_totals_do_not_block(self):
        from .services.plan_access import limit_reply, record_usage

        user = User.objects.create_user("tok", email="tok@example.com", password="userpass123")
        AppSetting.objects.update_or_create(
            pk=1,
            defaults={
                "plan_access": self._access(monthly_requests=0, input_tokens=100, output_tokens=100),
                "not_found_message": "Missing.",
            },
        )
        record_usage(user, {"input_tokens": 999, "output_tokens": 999, "cached_tokens": 999})
        self.assertEqual(limit_reply(user), "")

    def test_chat_uses_the_model_the_user_selected(self):
        from unittest.mock import patch

        from .services.chat_service import generate_reply

        user = User.objects.create_user("lee2", email="lee2@example.com", password="leepass123")
        AppSetting.objects.update_or_create(
            pk=1,
            defaults={"plan_access": self._access(input_tokens=0), "not_found_message": "Missing.", "openrouter_api_key": "test-key"},
        )
        UserChatSetting.objects.create(user=user, selected_model="openai/gpt-4o-mini")
        conversation = Conversation.objects.create(owner=user, title="Plan chat")
        client = APIClient()
        client.force_authenticate(user=user)
        def fake_complete(user, **kwargs):
            from .services.plan_access import record_usage

            record_usage(user, {"input_tokens": 2, "output_tokens": 1, "cached_tokens": 0})
            return {
                "content": "Hello",
                "usage": {"input_tokens": 2, "output_tokens": 1, "cached_tokens": 0},
                "blocked": False,
            }

        with patch(
            "chatbot.services.chat_service.complete_for_user",
            side_effect=fake_complete,
        ) as chat, patch("chatbot.services.plan_access.send_limit_email", return_value=True) as mailer:
            first = generate_reply(user, conversation, "Hi there", strict=False)
            second = generate_reply(user, conversation, "Again", strict=False)
        self.assertEqual(first.content, "Hello")
        self.assertEqual(chat.call_args.kwargs["model"], "openai/gpt-4o-mini")
        self.assertEqual(second.content, "Basic limit reached.")
        self.assertEqual(chat.call_count, 1)
        mailer.assert_called_once()
        status = client.get("/api/system/ollama/").json()
        self.assertEqual(status["provider"], "openrouter")
        self.assertEqual(status["chat_model"], "openai/gpt-4o-mini")

    def test_admin_plan_inputs_reach_the_user_menu(self):
        admin = User.objects.create_user("RRGupta", password="password123")
        person = User.objects.create_user("sam", password="sampass123")
        access = self._access(monthly_requests=10, input_tokens=100, output_tokens=50, cached_tokens=25)
        access["basic"]["model_names"] = {
            "openai/gpt-4o": "GPT-4o",
            "openai/gpt-4o-mini": "GPT-4o mini",
        }
        client = APIClient()
        client.force_authenticate(user=admin)
        saved = client.patch("/api/admin-settings/", {"plan_access": access}, format="json")
        self.assertEqual(saved.status_code, 200)
        basic = saved.json()["plan_access"]["basic"]
        self.assertEqual(basic["monthly_requests"], 10)
        self.assertEqual(basic["input_tokens"], 100)
        self.assertEqual(basic["output_tokens"], 50)
        self.assertEqual(basic["cached_tokens"], 25)
        self.assertEqual(basic["model_names"]["openai/gpt-4o-mini"], "GPT-4o mini")
        self.assertEqual(saved.json()["plan_access"]["silver"]["monthly_requests"], 20)
        self.assertEqual(saved.json()["plan_access"]["gold"]["monthly_requests"], 30)
        self.assertEqual(saved.json()["plan_access"]["diamond"]["monthly_requests"], 40)

        user_client = APIClient()
        user_client.force_authenticate(user=person)
        plan = user_client.get("/api/my-plan/").json()
        names = {row["id"]: row["name"] for row in plan["models"]}
        self.assertEqual(names["openai/gpt-4o"], "GPT-4o")
        chosen = user_client.patch("/api/my-plan/", {"selected_model": "openai/gpt-4o-mini"}, format="json")
        self.assertEqual(chosen.status_code, 200)
        self.assertEqual(chosen.json()["selected_model"], "openai/gpt-4o-mini")

    def test_openrouter_catalog_requests_five_hundred_models(self):
        from unittest.mock import MagicMock, patch

        from .services import openrouter_service

        openrouter_service._catalog.update(at=0.0, items=[], key="")
        AppSetting.objects.update_or_create(
            pk=1,
            defaults={"openrouter_api_key": "sk-or-test-1234567890", "not_found_message": "Missing."},
        )
        payload = MagicMock()
        payload.status_code = 200
        payload.text = ""
        payload.json.return_value = {
            "data": [
                {"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000},
                {"id": "openai/gpt-4o", "name": "duplicate"},
            ]
        }
        with patch("chatbot.services.openrouter_service.requests.get", return_value=payload) as get:
            rows = openrouter_service.list_models("")
        self.assertEqual(rows, [{"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000}])
        self.assertEqual(get.call_args.kwargs["params"], {"limit": 500})
        self.assertTrue(str(get.call_args.args[0]).endswith("/models"))
        openrouter_service._catalog.update(at=0.0, items=[], key="")


class ErrorLogTests(TestCase):
    def test_ui_error_stores_user_and_screenshot(self):
        import tempfile
        from pathlib import Path

        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings

        from chatbot.models import ErrorEvent

        user = User.objects.create_user("lee", email="lee@example.com", password="lee-pass-123")
        client = APIClient()
        client.force_authenticate(user=user)
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
        shot = SimpleUploadedFile("ui.png", png, content_type="image/png")
        with tempfile.TemporaryDirectory() as folder:
            with override_settings(ERROR_SCREENSHOT_DIR=folder):
                response = client.post(
                    "/api/client-errors/",
                    {
                        "message": "Widget failed",
                        "stack": "Error: Widget failed\n    at EmbedWidget",
                        "path": "/embed?bot=1",
                        "screenshot": shot,
                    },
                    format="multipart",
                )
            self.assertEqual(response.status_code, 201)
            row = ErrorEvent.objects.get(pk=response.json()["id"])
            self.assertEqual(row.username, "lee")
            self.assertEqual(row.email, "lee@example.com")
            self.assertEqual(row.user_id, user.id)
            self.assertIn("EmbedWidget", row.stack)
            self.assertTrue(row.screenshot_path)
            self.assertTrue(Path(row.screenshot_path).is_file())
            saved = Path(row.screenshot_path).read_bytes()
            self.assertTrue(saved.startswith(b"\x89PNG"))

    def test_backend_exception_stores_the_call_stack(self):
        from chatbot.services.error_log import record_exception

        class BrokenRequest:
            path = "/api/embed/x/"
            method = "GET"
            user = User.objects.create_user("sam", email="sam@example.com", password="sam-pass-123")
            META = {"HTTP_USER_AGENT": "test-agent"}

        try:
            raise RuntimeError("chat table missing")
        except RuntimeError as exc:
            row = record_exception(BrokenRequest(), exc, status_code=500)
        self.assertIsNotNone(row)
        self.assertIn("chat table missing", row.stack)
        self.assertIn("RuntimeError", row.stack)
        self.assertEqual(row.username, "sam")
        self.assertEqual(row.source, "backend")


class AdminDatabaseRouterTests(SimpleTestCase):
    def test_settings_and_errors_use_the_admin_database(self):
        from django.conf import settings

        from chatbot.models import AppSetting, ErrorEvent
        from chatbot.tenant_router import TenantRouter

        settings.DATABASES["admin"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": "unused"}
        try:
            router = TenantRouter()
            self.assertEqual(router.db_for_read(AppSetting), "admin")
            self.assertEqual(router.db_for_write(ErrorEvent), "admin")
            self.assertIsNone(router.db_for_read(Conversation))
            self.assertFalse(router.allow_migrate("default", "chatbot", model_name="appsetting"))
            self.assertTrue(router.allow_migrate("admin", "chatbot", model_name="errorevent"))
            self.assertFalse(router.allow_migrate("admin", "chatbot", model_name="conversation"))
        finally:
            del settings.DATABASES["admin"]


class PromptGatewayTests(TestCase):
    def test_prompt_render_requires_variables(self):
        from chatbot.services.prompt_service import render_template

        with self.assertRaises(ValueError):
            render_template("Hello {{name}}", {})

    def test_projected_limit_blocks_before_provider(self):
        from chatbot.models import AppSetting
        from chatbot.services.plan_access import projected_limit_block

        user = User.objects.create_user("cap", password="cap-pass-123")
        access = PlanLimitTests()._access(input_tokens=100, monthly_requests=0)
        AppSetting.objects.update_or_create(
            pk=1,
            defaults={"plan_access": access, "not_found_message": "Missing."},
        )
        self.assertEqual(projected_limit_block(user, 150), access["basic"]["limit_message"])
        self.assertEqual(projected_limit_block(user, 40), "")

    def test_gateway_passes_max_tokens_to_openrouter(self):
        from unittest.mock import patch

        from chatbot.services.llm_gateway import complete_for_user

        user = User.objects.create_user("max", password="max-pass-123")
        with patch(
            "chatbot.services.llm_gateway.complete_chat",
            return_value={"content": "ok", "usage": {"input_tokens": 1, "output_tokens": 1, "cached_tokens": 0}},
        ) as chat:
            complete_for_user(
                user,
                workflow="chat.reply",
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": "Hi"}],
                inline_system="Test",
            )
        self.assertIn("max_tokens", chat.call_args.kwargs)
        self.assertGreater(chat.call_args.kwargs["max_tokens"], 0)
