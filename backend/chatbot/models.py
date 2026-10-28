import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
        db_constraint=False,
    )
    title = models.CharField(max_length=200, default="New conversation")
    embed_bot = models.ForeignKey(
        "EmbedBot",
        on_delete=models.CASCADE,
        related_name="conversations",
        null=True,
        blank=True,
        db_constraint=False,
    )
    visitor_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "-updated_at"], name="chatbot_con_owner_i_b82d5f_idx"),
            models.Index(fields=["embed_bot", "visitor_id"], name="chatbot_con_embed_b_6a0c1d_idx"),
        ]


class Message(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"
    ROLE_CHOICES = [
        (ROLE_USER, "user"),
        (ROLE_ASSISTANT, "assistant"),
        (ROLE_SYSTEM, "system"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]


class FolderSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    root_path = models.CharField(max_length=1024)
    extensions = models.CharField(
        max_length=512, default=".pdf,.docx,.xlsx,.csv,.txt,.md,.json"
    )
    max_size_mb = models.IntegerField(default=25)
    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]


class Document(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "pending"),
        (STATUS_PROCESSING, "processing"),
        (STATUS_READY, "ready"),
        (STATUS_FAILED, "failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )
    folder_source = models.ForeignKey(
        FolderSource,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/%Y/%m/", blank=True)
    source_path = models.CharField(max_length=2048, blank=True)
    file_type = models.CharField(max_length=16, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.TextField(blank=True)
    size = models.BigIntegerField(default=0)
    page_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["folder_source"]),
        ]

    @property
    def is_shared(self) -> bool:
        return self.folder_source_id is not None


class DocumentChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.IntegerField()
    content = models.TextField()
    page = models.IntegerField(null=True, blank=True)
    embedding = models.TextField(blank=True, default="")  # JSON-encoded list[float]
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("document", "chunk_index")]
        indexes = [models.Index(fields=["document", "chunk_index"])]


class IndexingJob(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "pending"),
        (STATUS_RUNNING, "running"),
        (STATUS_DONE, "done"),
        (STATUS_FAILED, "failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folder_source = models.ForeignKey(
        FolderSource, on_delete=models.CASCADE, related_name="jobs"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    files_total = models.IntegerField(default=0)
    files_indexed = models.IntegerField(default=0)
    files_failed = models.IntegerField(default=0)
    message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]


class EmbedBot(models.Model):
    """Public widget a third-party site can open with a chatbot id."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="embed_bots"
    )
    name = models.CharField(max_length=80, default="Assistant")
    greeting = models.TextField(
        default="Hello! How can I help you today?"
    )
    quick_replies = models.JSONField(default=list, blank=True)
    accent = models.CharField(max_length=16, default="#2563eb")
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]


class DataConnection(models.Model):
    """A database the owner connects with a connection string. The chatbot reads it."""

    ENGINE_SQLITE = "sqlite"
    ENGINE_MYSQL = "mysql"
    ENGINE_POSTGRES = "postgresql"
    ENGINE_MSSQL = "mssql"
    ENGINE_CHOICES = [
        (ENGINE_SQLITE, "SQLite"),
        (ENGINE_MYSQL, "MySQL"),
        (ENGINE_POSTGRES, "PostgreSQL"),
        (ENGINE_MSSQL, "SQL Server"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="data_connections"
    )
    name = models.CharField(max_length=120)
    engine = models.CharField(max_length=16, choices=ENGINE_CHOICES)
    connection_string = models.TextField()
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]


class SqlKeywordQuery(models.Model):
    """When a chat message contains a keyword, run this read-only SQL."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sql_queries"
    )
    connection = models.ForeignKey(
        DataConnection, on_delete=models.CASCADE, related_name="queries"
    )
    name = models.CharField(max_length=120)
    keywords = models.JSONField(default=list, blank=True)
    sql_text = models.TextField()
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]


class IntakeQuestion(models.Model):
    """A question the chatbot asks before the conversation starts."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="intake_questions"
    )
    label = models.CharField(max_length=80)
    field_key = models.CharField(max_length=40)
    placeholder = models.CharField(max_length=120, blank=True, default="")
    required = models.BooleanField(default=True)
    position = models.IntegerField(default=0)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "field_key"], name="chatbot_intake_owner_key"
            )
        ]


class VisitorProfile(models.Model):
    """Answers collected before a chat. Used for later analysis, not as knowledge."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.OneToOneField(
        Conversation, on_delete=models.CASCADE, related_name="profile"
    )
    answers = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class WebSource(models.Model):
    """A public website the admin crawled into this user's vector collection."""

    STATUS_PENDING = "pending"
    STATUS_CRAWLING = "crawling"
    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "pending"),
        (STATUS_CRAWLING, "crawling"),
        (STATUS_READY, "ready"),
        (STATUS_FAILED, "failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="web_sources"
    )
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    enabled = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.TextField(blank=True)
    message = models.CharField(max_length=300, blank=True, default="")
    page_count = models.IntegerField(default=0)
    chunk_count = models.IntegerField(default=0)
    max_pages = models.IntegerField(default=300)
    crawl_token = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "-updated_at"], name="chatbot_web_owner_u_idx")
        ]


class WebPage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(WebSource, on_delete=models.CASCADE, related_name="pages")
    url = models.URLField(max_length=500)
    title = models.CharField(max_length=300, blank=True, default="")
    chunk_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["url"]
        constraints = [
            models.UniqueConstraint(fields=["source", "url"], name="chatbot_webpage_source_url")
        ]


def default_plan_days():
    return {"basic": 0, "silver": 0, "gold": 0, "diamond": 0}


def default_plan_access():
    requests = {"basic": 10, "silver": 20, "gold": 30, "diamond": 40}
    labels = {"basic": "Basic", "silver": "Silver", "gold": "Gold", "diamond": "Diamond"}
    return {
        key: {
            "days": 0,
            "models": [],
            "monthly_requests": requests[key],
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "limit_message": f"You have reached the {labels[key]} plan limit for this month.",
        }
        for key in requests
    }


class AppSetting(models.Model):
    """One row. A day count of 0 means automatic deletion is off."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    retention_days = models.PositiveIntegerField(default=0)
    plan_days = models.JSONField(default=default_plan_days)
    plan_access = models.JSONField(default=default_plan_access)
    openrouter_api_key = models.CharField(max_length=300, blank=True, default="")
    mail_settings = models.JSONField(default=dict, blank=True)
    not_found_message = models.TextField(
        default="I could not find that in your uploaded files or websites."
    )
    last_purge_at = models.DateTimeField(null=True, blank=True)
    llm_policy = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "app setting"


def default_llm_policy():
    return {
        "default_max_output_tokens": 2048,
        "default_max_input_tokens_per_request": 0,
        "missing_plan_policy": "defaults",
    }


class PromptTemplate(models.Model):
    """Admin-managed LLM instruction text keyed by workflow slug."""

    slug = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=64, default="chat")
    workflow = models.CharField(max_length=64, default="chat")
    description = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    active_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by_id = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["category", "slug"]
        verbose_name = "prompt template"


class PromptVersion(models.Model):
    prompt = models.ForeignKey(
        PromptTemplate, on_delete=models.CASCADE, related_name="versions"
    )
    version = models.PositiveIntegerField()
    content = models.TextField()
    variables = models.JSONField(default=list, blank=True)
    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by_id = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["prompt", "version"], name="chatbot_prompt_version_unique"
            )
        ]
        verbose_name = "prompt version"


class LlmUsageLog(models.Model):
    """One LLM completion attempt for cost and token observability."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="llm_usage"
    )
    workflow = models.CharField(max_length=64)
    provider = models.CharField(max_length=32, default="openrouter")
    model = models.CharField(max_length=120, blank=True, default="")
    prompt_slug = models.CharField(max_length=80, blank=True, default="")
    prompt_version = models.PositiveIntegerField(default=0)
    estimated_input_tokens = models.PositiveIntegerField(default=0)
    actual_input_tokens = models.PositiveIntegerField(default=0)
    max_output_tokens = models.PositiveIntegerField(default=0)
    actual_output_tokens = models.PositiveIntegerField(default=0)
    cached_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=True)
    error_message = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["workflow", "-created_at"]),
        ]
        verbose_name = "LLM usage log"


class ErrorEvent(models.Model):
    """A backend or UI failure, including the call stack and any screenshot file."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=16)
    path = models.CharField(max_length=500, blank=True, default="")
    method = models.CharField(max_length=16, blank=True, default="")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    message = models.TextField(blank=True, default="")
    stack = models.TextField(blank=True, default="")
    user_id = models.IntegerField(null=True, blank=True)
    username = models.CharField(max_length=150, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    user_agent = models.CharField(max_length=400, blank=True, default="")
    screenshot_path = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "error event"


class UserProfile(models.Model):
    """Plan and the private database created for this account."""

    PLAN_BASIC = "basic"
    PLAN_SILVER = "silver"
    PLAN_GOLD = "gold"
    PLAN_DIAMOND = "diamond"
    PLAN_CHOICES = [
        (PLAN_BASIC, "Basic"),
        (PLAN_SILVER, "Silver"),
        (PLAN_GOLD, "Gold"),
        (PLAN_DIAMOND, "Diamond"),
    ]
    PLANS = (PLAN_BASIC, PLAN_SILVER, PLAN_GOLD, PLAN_DIAMOND)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant"
    )
    plan = models.CharField(max_length=16, choices=PLAN_CHOICES, default=PLAN_BASIC)
    database_name = models.CharField(max_length=63, unique=True)
    engine = models.CharField(max_length=16, default="sqlite")
    ready = models.BooleanField(default=False)
    error = models.TextField(blank=True, default="")
    migrated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "user profile"


class UserChatSetting(models.Model):
    """Per-user reply used when that account's chatbot finds no information."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_setting"
    )
    not_found_message = models.TextField(blank=True, default="")
    selected_model = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        verbose_name = "user chat setting"


class MonthlyUsage(models.Model):
    """Token and request totals for one account during one calendar month."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monthly_usage"
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    requests = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cached_tokens = models.PositiveIntegerField(default=0)
    email_sent = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "year", "month"], name="chatbot_usage_user_month"
            )
        ]


class DatabaseRecord(models.Model):
    """Reference rows the assistant can answer from, separate from uploaded files."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=64)
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "title"]