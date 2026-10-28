from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AppSetting, Conversation, Document, Message, UserChatSetting, WebSource
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
        self.assertEqual(r.status_code, 404)

    def test_document_list_is_isolated(self):
        r = self._client(self.alice).get("/api/documents/")
        self.assertEqual(r.status_code, 200)
        titles = [x["title"] for x in r.json()["results"]]
        self.assertIn("Alice doc", titles)
        self.assertNotIn("Bob doc", titles)

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