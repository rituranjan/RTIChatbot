"""Local embeddings for website pages. Separate from the chat model's provider."""
import os
import threading

from django.conf import settings

_lock = threading.Lock()
_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            os.environ["FASTEMBED_CACHE_PATH"] = settings.FASTEMBED_CACHE_PATH
            from fastembed import TextEmbedding

            _model = TextEmbedding(model_name=settings.WEB_EMBED_MODEL)
    return _model


def _floats(vector) -> list[float]:
    return [float(value) for value in vector]


def embed_passages(texts: list[str]) -> list[list[float]]:
    rows = [text.strip() for text in texts if text and text.strip()]
    if not rows:
        return []
    model = _get_model()
    embed = getattr(model, "passage_embed", None) or model.embed
    return [_floats(vector) for vector in embed(rows)]


def embed_query(text: str) -> list[float]:
    model = _get_model()
    query_embed = getattr(model, "query_embed", None)
    vector = next((query_embed or model.embed)([text]))
    return _floats(vector)
