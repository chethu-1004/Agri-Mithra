import json
import math
from pathlib import Path

from agrinetra.config import settings


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path.cwd() / path


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


async def retrieve_evidence(query: str, limit: int = 4) -> list[dict]:
    """Optionally retrieve pre-indexed, locally stored agricultural document chunks."""
    if not settings.agri_rag_enabled:
        return []
    index_path = _resolve(settings.agri_rag_index_path)
    if not index_path.is_file():
        return []
    api_key = settings.openai_api_key or settings.chatbot_api_key
    if not api_key:
        return []
    try:
        index = json.loads(index_path.read_text(encoding='utf-8'))
        chunks = index.get('chunks', []) if isinstance(index, dict) else []
        if not chunks:
            return []
        from openai import AsyncOpenAI
        async with AsyncOpenAI(
            api_key=api_key,
            base_url=settings.openai_base_url or settings.chatbot_base_url or None,
            timeout=max(5.0, min(float(settings.chatbot_timeout_seconds), 60.0)),
            max_retries=0,
        ) as client:
            response = await client.embeddings.create(
                model=settings.openai_embedding_model,
                input=query[:4000],
            )
        query_embedding = response.data[0].embedding
        ranked = sorted(
            (
                (cosine_similarity(query_embedding, row.get('embedding') or []), row)
                for row in chunks
                if isinstance(row, dict) and isinstance(row.get('text'), str)
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        return [
            {'source': row.get('source', 'Agricultural reference'), 'text': row['text']}
            for score, row in ranked[:max(1, min(limit, 6))]
            if score >= 0.15
        ]
    except Exception:
        # RAG remains optional; a missing/corrupt index or embedding outage must not disable chat.
        return []
