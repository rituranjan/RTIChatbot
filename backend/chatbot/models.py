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
        constraints = [
            models.UniqueConstraint(
                fields=["embed_bot", "visitor_id"],
                condition=models.Q(embed_bot__isnull=False) & ~models.Q(visitor_id=""),
                name="chatbot_embed_visitor_unique",
            ),
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


class EmbedVisitorSession(models.Model):
    """Tracks active embed visitors for per-plan concurrent user limits (default DB)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="embed_sessions",
    )
    visitor_id = models.CharField(max_length=64)
    embed_bot = models.ForeignKey(
        EmbedBot,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="visitor_sessions",
    )
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "visitor_id"],
                name="chatbot_embed_session_owner_visitor",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "-last_seen"], name="chatbot_embed_sess_seen_idx"),
        ]


class EmbedAllowedDomain(models.Model):
    """Hostnames allowed to embed the widget (parent page origin)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="embed_domains",
    )
    host = models.CharField(max_length=253)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "host"],
                name="chatbot_embed_domain_owner_host",
            ),
        ]
        ordering = ["host"]


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
            models.UniqueConstraint(fields=["source", "url"], name="chatbot_webpage_source_url"),
        ]


class WebRagPage(models.Model):
    """A single public page indexed for RAG (paste URL list), separate from full-site crawls."""

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
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="web_rag_pages"
    )
    url = models.URLField(max_length=500)
    title = models.CharField(max_length=300, blank=True, default="")
    enabled = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.TextField(blank=True)
    message = models.CharField(max_length=300, blank=True, default="")
    chunk_count = models.IntegerField(default=0)
    priority = models.IntegerField(default=100)
    index_token = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "-updated_at"], name="chatbot_ragpage_owner_u_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["owner", "url"], name="chatbot_ragpage_owner_url_uniq"),
        ]


def default_semantic_sql_settings():
    return {
        "platform_enabled": True,
        "default_max_rows": 40,
        "default_timeout_seconds": 12,
        "use_llm_understanding": True,
        "fallback_keyword_sql": True,
    }


class SemanticEngineConfig(models.Model):
    """Per-workspace (owner) semantic text-to-SQL settings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="semantic_engine"
    )
    connection = models.ForeignKey(
        "DataConnection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_engines",
    )
    report_query = models.ForeignKey(
        "SqlKeywordQuery",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_reports",
        help_text="Canonical SELECT from SQL keywords; uses that query's database connection.",
    )
    enabled = models.BooleanField(default=False)
    database_name = models.CharField(max_length=120, blank=True, default="")
    base_from_sql = models.TextField(blank=True, default="")
    tenant_filter_column = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Optional physical column (e.g. a.user_id) always filtered to workspace.",
    )
    max_rows = models.PositiveIntegerField(default=40)
    timeout_seconds = models.PositiveIntegerField(default=12)
    use_llm_understanding = models.BooleanField(default=True)
    fallback_keyword_sql = models.BooleanField(default=True)
    temperature = models.FloatField(default=0.0)
    MODE_KEYWORDS = "keywords"
    MODE_SEMANTIC = "semantic"
    MODE_CHOICES = [(MODE_KEYWORDS, "keywords"), (MODE_SEMANTIC, "semantic")]
    chat_sql_mode = models.CharField(max_length=16, choices=MODE_CHOICES, default=MODE_KEYWORDS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SemanticTable(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="semantic_tables"
    )
    database_name = models.CharField(max_length=120)
    table_name = models.CharField(max_length=120)
    table_alias = models.CharField(max_length=16, blank=True, default="")
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["table_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "database_name", "table_name"],
                name="chatbot_sem_table_owner_db_name",
            )
        ]


class SemanticColumn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    semantic_table = models.ForeignKey(
        SemanticTable, on_delete=models.CASCADE, related_name="columns"
    )
    physical_column = models.CharField(max_length=200)
    sql_alias = models.CharField(max_length=200, blank=True, default="")
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    data_type = models.CharField(max_length=64, blank=True, default="string")
    searchable = models.BooleanField(default=True)
    filterable = models.BooleanField(default=True)
    sortable = models.BooleanField(default=True)
    groupable = models.BooleanField(default=False)
    aggregatable = models.BooleanField(default=False)
    sensitive = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["physical_column"]
        constraints = [
            models.UniqueConstraint(
                fields=["semantic_table", "physical_column"],
                name="chatbot_sem_col_table_phys",
            )
        ]


class SemanticSynonym(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    semantic_column = models.ForeignKey(
        SemanticColumn, on_delete=models.CASCADE, related_name="synonyms"
    )
    synonym = models.CharField(max_length=200)
    language_code = models.CharField(max_length=16, blank=True, default="en")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["synonym"]
        constraints = [
            models.UniqueConstraint(
                fields=["semantic_column", "synonym", "language_code"],
                name="chatbot_sem_syn_col_lang",
            )
        ]


class SemanticRelationship(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="semantic_relationships"
    )
    source_table = models.CharField(max_length=120)
    source_column = models.CharField(max_length=200)
    target_table = models.CharField(max_length=120)
    target_column = models.CharField(max_length=200)
    join_type = models.CharField(max_length=16, default="LEFT")
    join_condition = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["source_table"]


class SemanticExample(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="semantic_examples"
    )
    question = models.TextField()
    expected_columns = models.JSONField(default=list, blank=True)
    expected_filters = models.JSONField(default=list, blank=True)
    expected_query_pattern = models.TextField(blank=True, default="")
    language_code = models.CharField(max_length=16, blank=True, default="en")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SemanticSchemaSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="semantic_snapshots"
    )
    connection = models.ForeignKey(
        DataConnection, on_delete=models.CASCADE, related_name="semantic_snapshots"
    )
    payload = models.JSONField(default=dict, blank=True)
    reviewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


def default_plan_days():
    return {"basic": 0, "silver": 0, "gold": 0, "diamond": 0}


def default_plan_access():
    requests = {"basic": 10, "silver": 20, "gold": 30, "diamond": 40}
    labels = {"basic": "Basic", "silver": "Silver", "gold": "Gold", "diamond": "Diamond"}
    website_rag_sites = {"basic": 1, "silver": 2, "gold": 5, "diamond": 10}
    language_on = {"basic": False, "silver": True, "gold": True, "diamond": True}
    sql_keyword_on = {"basic": True, "silver": True, "gold": True, "diamond": True}
    semantic_sql_on = {"basic": True, "silver": True, "gold": True, "diamond": True}
    concurrent = {"basic": 1, "silver": 2, "gold": 5, "diamond": 10}
    max_domains = {"basic": 1, "silver": 2, "gold": 5, "diamond": 10}
    return {
        key: {
            "days": 0,
            "models": [],
            "monthly_requests": requests[key],
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "website_max_pages": website_rag_sites[key],
            "language_enabled": language_on[key],
            "sql_keyword_enabled": sql_keyword_on[key],
            "semantic_sql_enabled": semantic_sql_on[key],
            "concurrent_users": concurrent[key],
            "max_embed_domains": max_domains[key],
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
    language_settings = models.JSONField(default=dict, blank=True)
    semantic_sql_settings = models.JSONField(default=default_semantic_sql_settings, blank=True)

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
            models.Index(fields=["user", "-created_at"], name="chatbot_llm_user_created_idx"),
            models.Index(fields=["workflow", "-created_at"], name="chatbot_llm_wf_created_idx"),
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
    preferred_language = models.CharField(max_length=16, blank=True, default="")

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