"""Build a local vector index from trusted Markdown and text documents."""
import asyncio
import json
import os
from pathlib import Path

from agrinetra.config import settings


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path.cwd() / path


def chunk_documents(documents_dir: Path, max_chars: int = 1400, overlap: int = 180) -> list[dict]:
    rows = []
    for path in sorted(documents_dir.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.md', '.txt'}:
            continue
        text = path.read_text(encoding='utf-8-sig', errors='replace').strip()
        if not text:
            continue
        paragraphs = [part.strip() for part in text.split('\n\n') if part.strip()]
        pieces: list[str] = []
        current = ''
        for paragraph in paragraphs:
            if len(paragraph) > max_chars:
                if current:
                    pieces.append(current)
                    current = ''
                start = 0
                while start < len(paragraph):
                    pieces.append(paragraph[start:start + max_chars])
                    start += max(1, max_chars - overlap)
                continue
            candidate = f'{current}\n\n{paragraph}' if current else paragraph
            if len(candidate) > max_chars:
                pieces.append(current)
                current = paragraph
            else:
                current = candidate
        if current:
            pieces.append(current)
        source = path.relative_to(documents_dir).as_posix()
        rows.extend(
            {'source': source, 'chunk': index + 1, 'text': content}
            for index, content in enumerate(pieces)
        )
    return rows


async def build_index() -> Path:
    api_key = settings.openai_api_key or settings.chatbot_api_key
    if not api_key:
        raise RuntimeError('Set OPENAI_API_KEY in backend/backend/.env before building the optional RAG index.')
    documents_dir = _resolve(settings.agri_rag_documents_dir)
    chunks = chunk_documents(documents_dir)
    if not chunks:
        raise RuntimeError(f'Add trusted .md or .txt references under {documents_dir} before indexing.')
    from openai import AsyncOpenAI
    async with AsyncOpenAI(
        api_key=api_key,
        base_url=settings.openai_base_url or settings.chatbot_base_url or None,
        timeout=max(5.0, min(float(settings.chatbot_timeout_seconds), 90.0)),
        max_retries=0,
    ) as client:
        for start in range(0, len(chunks), 64):
            batch = chunks[start:start + 64]
            response = await client.embeddings.create(
                model=settings.openai_embedding_model,
                input=[item['text'] for item in batch],
            )
            for item, embedded in zip(batch, response.data):
                item['embedding'] = embedded.embedding
    index_path = _resolve(settings.agri_rag_index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = index_path.with_suffix(index_path.suffix + '.tmp')
    temporary.write_text(
        json.dumps({'embedding_model': settings.openai_embedding_model, 'chunks': chunks}, ensure_ascii=False),
        encoding='utf-8',
    )
    os.replace(temporary, index_path)
    return index_path


if __name__ == '__main__':
    destination = asyncio.run(build_index())
    print(f'Indexed trusted agricultural references to {destination}')
