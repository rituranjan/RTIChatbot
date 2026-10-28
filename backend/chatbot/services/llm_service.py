"""Chat and embedding calls for the provider selected in .env."""
import requests
from django.conf import settings

from .ollama_service import OllamaError, OllamaService


def _refresh():
    reload = getattr(settings, "reload_runtime_env", None)
    if reload:
        reload()


class LLMError(Exception):
    pass


def _messages(messages, system_prompt):
    payload = []
    if system_prompt:
        payload.append({"role": "system", "content": system_prompt})
    for message in messages or []:
        role = message.get("role") or "user"
        if role not in ("system", "user", "assistant"):
            role = "user"
        payload.append({"role": role, "content": message.get("content") or ""})
    return payload


class _HttpChat:
    def __init__(self, provider):
        self.provider = provider
        self.timeout = settings.OLLAMA_TIMEOUT
        self.connect_timeout = settings.OLLAMA_CONNECT_TIMEOUT

    def chat(self, messages, system_prompt=None, temperature=0.2) -> str:
        url, headers, body = self._chat_request(messages, system_prompt, temperature)
        try:
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=(self.connect_timeout, self.timeout),
            )
        except requests.exceptions.Timeout as exc:
            raise LLMError(f"{self.provider} request timed out.") from exc
        except requests.RequestException as exc:
            raise LLMError(f"{self.provider} request failed: {exc}") from exc
        if response.status_code >= 400:
            detail = response.text[:500]
            raise LLMError(f"{self.provider} request failed ({response.status_code}): {detail}")
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        return ((choices[0].get("message") or {}).get("content") or "").strip()

    def embed(self, text: str):
        url, headers, body = self._embed_request(text)
        try:
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=(self.connect_timeout, self.timeout),
            )
            response.raise_for_status()
            rows = response.json().get("data") or []
            if not rows:
                return []
            return rows[0].get("embedding") or []
        except requests.RequestException as exc:
            raise LLMError(f"{self.provider} embedding failed: {exc}") from exc


class AzureService(_HttpChat):
    def __init__(self):
        super().__init__("Azure")
        self.endpoint = settings.AZURE_ENDPOINT
        self.api_key = settings.AZURE_API_KEY
        self.api_version = settings.AZURE_API_VERSION
        self.chat_deployment = settings.AZURE_CHAT_DEPLOYMENT
        self.embedding_deployment = settings.AZURE_EMBEDDING_DEPLOYMENT

    def _require(self, deployment, purpose):
        if not self.endpoint or not self.api_key or not deployment:
            raise LLMError(
                "Azure is not configured. Set AZURE_ENDPOINT, API_KEY, "
                f"and {purpose} (or MODEL_NAME) in backend/.env."
            )

    def _url(self, deployment):
        return (
            f"{self.endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self.api_version}"
        )

    def _headers(self):
        return {"api-key": self.api_key, "Content-Type": "application/json"}

    def _chat_request(self, messages, system_prompt, temperature):
        self._require(self.chat_deployment, "AZURE_CHAT_DEPLOYMENT")
        body = {
            "messages": _messages(messages, system_prompt),
            "temperature": temperature,
        }
        return self._url(self.chat_deployment), self._headers(), body

    def _embed_request(self, text):
        self._require(self.embedding_deployment, "AZURE_EMBEDDING_DEPLOYMENT")
        url = (
            f"{self.endpoint}/openai/deployments/{self.embedding_deployment}/embeddings"
            f"?api-version={self.api_version}"
        )
        return url, self._headers(), {"input": text}

    def configured(self) -> bool:
        return bool(self.endpoint and self.api_key and self.chat_deployment)

    @property
    def model_name(self) -> str:
        return self.chat_deployment or "(set AZURE_CHAT_DEPLOYMENT)"


class OpenAIService(_HttpChat):
    def __init__(self):
        super().__init__("ChatGPT")
        self.base_url = settings.OPENAI_BASE_URL
        self.api_key = settings.OPENAI_API_KEY
        self.chat_model = settings.OPENAI_CHAT_MODEL
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL

    def _headers(self):
        if not self.api_key:
            raise LLMError("ChatGPT is not configured. Set OPENAI_API_KEY in backend/.env.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _chat_request(self, messages, system_prompt, temperature):
        body = {
            "model": self.chat_model,
            "messages": _messages(messages, system_prompt),
            "temperature": temperature,
        }
        return f"{self.base_url}/chat/completions", self._headers(), body

    def _embed_request(self, text):
        body = {"model": self.embedding_model, "input": text}
        return f"{self.base_url}/embeddings", self._headers(), body

    def configured(self) -> bool:
        return bool(self.api_key and self.chat_model)

    @property
    def model_name(self) -> str:
        return self.chat_model


class _OllamaAdapter:
    def __init__(self):
        self.service = OllamaService()

    def chat(self, messages, system_prompt=None, temperature=0.2) -> str:
        try:
            return self.service.chat(messages, system_prompt=system_prompt, temperature=temperature)
        except OllamaError as exc:
            raise LLMError(str(exc)) from exc

    def embed(self, text: str):
        try:
            return self.service.embed(text)
        except OllamaError as exc:
            raise LLMError(str(exc)) from exc

    def configured(self) -> bool:
        return self.service.is_available()

    @property
    def model_name(self) -> str:
        return self.service.chat_model


def _provider(name: str):
    if name in ("azure",):
        return AzureService()
    if name in ("openai", "chatgpt"):
        return OpenAIService()
    return _OllamaAdapter()


def chat_service():
    _refresh()
    return _provider(settings.LLM_PROVIDER)


def embedding_service():
    _refresh()
    return _provider(settings.EMBEDDING_PROVIDER or "ollama")


def chat_completion(messages, system_prompt=None, temperature=0.2) -> str:
    return chat_service().chat(messages, system_prompt=system_prompt, temperature=temperature)


def embed_text(text: str):
    return embedding_service().embed(text)


def provider_status(user=None):
    _refresh()
    from .plan_access import openrouter_status

    chat = openrouter_status(user)
    embedding = embedding_service()
    return {
        "provider": "openrouter",
        "available": chat["configured"],
        "chat_model": chat.get("model_name") or chat["model"] or "not selected",
        "embedding_provider": settings.EMBEDDING_PROVIDER or "ollama",
        "embedding_model": (
            settings.OLLAMA_EMBEDDING_MODEL
            if (settings.EMBEDDING_PROVIDER or "ollama") == "ollama"
            else (
                settings.AZURE_EMBEDDING_DEPLOYMENT
                if settings.EMBEDDING_PROVIDER == "azure"
                else settings.OPENAI_EMBEDDING_MODEL
            )
        ),
        "embedding_configured": (
            embedding.configured()
            if (settings.EMBEDDING_PROVIDER or "ollama") != "ollama"
            else chat["configured"]
        ),
        "base_url": chat["base_url"],
        "chat_model_installed": None,
        "embedding_model_installed": None,
    }
