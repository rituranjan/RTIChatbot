import json
import requests
from django.conf import settings

class OllamaError(Exception):
    pass

class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.chat_model = settings.OLLAMA_CHAT_MODEL
        self.embedding_model = settings.OLLAMA_EMBEDDING_MODEL
        self.vision_model = settings.OLLAMA_VISION_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT
        self.connect_timeout = settings.OLLAMA_CONNECT_TIMEOUT

    def _url(self, path):
        return f"{self.base_url}{path}"

    def is_available(self):
        try:
            r = requests.get(self._url("/api/tags"), timeout=self.connect_timeout)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self):
        try:
            r = requests.get(self._url("/api/tags"), timeout=self.connect_timeout)
            r.raise_for_status()
            return [m.get("name") for m in r.json().get("models", [])]
        except requests.RequestException as exc:
            raise OllamaError(f"Cannot reach Ollama: {exc}")

    def chat(self, messages, system_prompt=None, model=None):
        payload = {
            "model": model or self.chat_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if system_prompt:
            payload["system"] = system_prompt
        try:
            r = requests.post(self._url("/api/chat"), json=payload, timeout=(self.connect_timeout, self.timeout))
            r.raise_for_status()
            data = r.json()
            return (data.get("message") or {}).get("content", "").strip()
        except requests.exceptions.Timeout:
            raise OllamaError("Ollama request timed out.")
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama request failed: {exc}")

    def embed(self, text, model=None):
        payload = {"model": model or self.embedding_model, "prompt": text}
        try:
            r = requests.post(self._url("/api/embeddings"), json=payload, timeout=(self.connect_timeout, self.timeout))
            r.raise_for_status()
            return r.json().get("embedding") or []
        except requests.RequestException as exc:
            raise OllamaError(f"Embedding request failed: {exc}")

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]

    def describe_image(self, image_path):
        if not self.vision_model:
            return None
        # Ollama vision: pass image as base64 in messages
        import base64
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        payload = {
            "model": self.vision_model,
            "messages": [{"role": "user", "content": "Describe this image in detail. Extract all visible text verbatim.", "images": [b64]}],
            "stream": False,
        }
        try:
            r = requests.post(self._url("/api/chat"), json=payload, timeout=(self.connect_timeout, self.timeout))
            r.raise_for_status()
            return (r.json().get("message") or {}).get("content", "").strip()
        except requests.RequestException:
            return None