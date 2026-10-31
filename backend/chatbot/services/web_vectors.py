"""One Qdrant collection per user. Website chunks for that user live only there."""
import uuid

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

_client = None


def collection_name(owner_id) -> str:
    return f"user-{owner_id}"


def qdrant() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.QDRANT_URL, timeout=30)
    return _client


def ensure_collection(owner_id, dimension: int) -> str:
    name = collection_name(owner_id)
    client = qdrant()
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )
    return name


def upsert_chunks(owner_id, website_id, rows: list[dict]) -> None:
    if not rows:
        return
    name = ensure_collection(owner_id, len(rows[0]["vector"]))
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=row["vector"],
            payload={
                "website_id": str(website_id),
                "url": row["url"],
                "title": row["title"],
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "priority": int(row.get("priority") or 0),
            },
        )
        for row in rows
    ]
    qdrant().upsert(collection_name=name, points=points)


def delete_website(owner_id, website_id) -> None:
    name = collection_name(owner_id)
    client = qdrant()
    if not client.collection_exists(name):
        return
    client.delete(
        collection_name=name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="website_id",
                    match=MatchValue(value=str(website_id)),
                )
            ]
        ),
    )


def delete_user_collection(owner_id) -> None:
    name = collection_name(owner_id)
    client = qdrant()
    if client.collection_exists(name):
        client.delete_collection(collection_name=name)


def search_websites(owner_id, vector: list[float], website_ids: list[str], limit: int):
    if not vector or not website_ids:
        return []
    name = collection_name(owner_id)
    client = qdrant()
    if not client.collection_exists(name):
        return []
    found = client.query_points(
        collection_name=name,
        query=vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="website_id",
                    match=MatchAny(any=[str(item) for item in website_ids]),
                )
            ]
        ),
        limit=limit,
        score_threshold=settings.RETRIEVAL_MIN_SCORE,
        with_payload=True,
    )
    rows = []
    for point in found.points:
        payload = point.payload or {}
        base_score = float(point.score or 0)
        priority = int(payload.get("priority") or 0)
        score = base_score + (priority / 1000.0)
        rows.append(
            {
                "website_id": payload.get("website_id") or "",
                "document_title": payload.get("title") or payload.get("url") or "Website",
                "url": payload.get("url") or "",
                "chunk_index": payload.get("chunk_index") or 0,
                "content": payload.get("content") or "",
                "score": round(score, 3),
            }
        )
    rows.sort(key=lambda item: item["score"], reverse=True)
    return rows
