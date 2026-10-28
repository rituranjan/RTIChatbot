import json
import math

from django.conf import settings
from django.db import transaction

from ..models import Document, DocumentChunk
from .document_parser import extract_text
from .llm_service import LLMError, embed_text


def split_text(text: str, chunk_size=None, overlap=None):
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = settings.CHUNK_OVERLAP if overlap is None else overlap
    if chunk_size <= overlap:
        overlap = max(0, chunk_size // 4)
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def pack_vector(vec) -> str:
    return json.dumps(vec or [])


def unpack_vector(s: str):
    if not s:
        return []
    try:
        return json.loads(s)
    except Exception:
        return []


def cosine(a, b) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def index_document(document: Document, text=None) -> int:
    if text is None:
        if document.file:
            path = document.file.path
        else:
            path = document.source_path
        text = extract_text(path)

    chunks = split_text(text)

    with transaction.atomic():
        document.chunks.all().delete()
        for i, chunk in enumerate(chunks):
            try:
                vec = embed_text(chunk)
            except LLMError:
                vec = []
            DocumentChunk.objects.create(
                document=document,
                chunk_index=i,
                content=chunk,
                embedding=pack_vector(vec),
            )
    return len(chunks)