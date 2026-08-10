"""
WhatsAppBusinessAI — RAG Pipeline: extract -> chunk -> embed -> retrieve

process_document() is the whole ingestion pipeline for one
KnowledgeDocument, run from a Celery task. retrieve_relevant_chunks() is
what apps.ai.services calls at reply time to ground the AI's system prompt
in real business content instead of only the business's own profile
fields (see docs/ai.md's "never invent" instruction — this is what
actually gives it something true to say).
"""

import io
import logging
import math
import re

from django.core.exceptions import ValidationError

from .models import KnowledgeChunk, KnowledgeDocument
from .providers import get_embedding_provider

logger = logging.getLogger("waba")

ALLOWED_FILE_EXTENSIONS = (".txt", ".pdf")
MAX_CHUNK_WORDS = 200
CHUNK_OVERLAP_WORDS = 30
DEFAULT_TOP_K = 3


def validate_file_extension(filename: str) -> None:
    lowered = filename.lower()
    if not lowered.endswith(ALLOWED_FILE_EXTENSIONS):
        raise ValidationError(
            f"Unsupported file type. Allowed: {', '.join(ALLOWED_FILE_EXTENSIONS)}."
        )


def extract_text(document: KnowledgeDocument) -> str:
    """Returns the document's plain text — from `raw_text` directly, or extracted from `file`."""
    if document.source_type == KnowledgeDocument.SourceType.TEXT:
        return document.raw_text

    filename = document.file.name.lower()
    document.file.open("rb")
    try:
        raw = document.file.read()
    finally:
        document.file.close()

    if filename.endswith(".pdf"):
        return _extract_pdf_text(raw)
    if filename.endswith(".txt"):
        return raw.decode("utf-8", errors="replace")
    raise ValidationError(f"Unsupported file type: {filename}")


def _extract_pdf_text(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def chunk_text(text: str) -> list[str]:
    """
    Splits `text` into overlapping word-count-bounded chunks. Word-based
    (not character-based) so a chunk boundary never lands mid-word, and
    overlap means a fact stated right at a chunk boundary is still fully
    present in at least one chunk instead of being split across two.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    step = MAX_CHUNK_WORDS - CHUNK_OVERLAP_WORDS
    while start < len(words):
        chunk_words = words[start : start + MAX_CHUNK_WORDS]
        chunks.append(" ".join(chunk_words))
        if start + MAX_CHUNK_WORDS >= len(words):
            break
        start += step
    return chunks


def process_document(document: KnowledgeDocument) -> None:
    """
    Extracts, chunks, and (if an embedding provider is configured) embeds
    a document. Replaces any chunks from a previous run, so re-processing
    (e.g. after a file was re-uploaded) is idempotent, not additive.
    """
    document.status = KnowledgeDocument.Status.PROCESSING
    document.save(update_fields=["status", "updated_at"])

    try:
        text = extract_text(document)
        if document.source_type == KnowledgeDocument.SourceType.UPLOAD:
            document.raw_text = text

        pieces = chunk_text(text)
        if not pieces:
            raise ValidationError("No extractable text found in this document.")

        document.chunks.all().delete()
        chunks = [
            KnowledgeChunk(tenant=document.tenant, document=document, chunk_index=i, content=piece)
            for i, piece in enumerate(pieces)
        ]
        KnowledgeChunk.objects.bulk_create(chunks)

        embedded_count = _embed_chunks(document)

        document.chunk_count = len(chunks)
        document.embedded_chunk_count = embedded_count
        document.status = KnowledgeDocument.Status.READY
        document.error_message = ""
        document.save(
            update_fields=[
                "raw_text",
                "chunk_count",
                "embedded_chunk_count",
                "status",
                "error_message",
                "updated_at",
            ]
        )
    except Exception as exc:
        logger.exception("Knowledge document %s failed to process.", document.id)
        document.status = KnowledgeDocument.Status.FAILED
        document.error_message = str(exc)[:2000]
        document.save(update_fields=["status", "error_message", "updated_at"])


def _embed_chunks(document: KnowledgeDocument) -> int:
    """
    Returns how many chunks got a real embedding. If no provider is
    configured (no OPENAI_API_KEY — genuinely the case this session),
    chunks are left with embedding=None and retrieval falls back to
    keyword matching for them; the document still becomes READY rather
    than FAILED, since it's fully usable in degraded mode.
    """
    provider = get_embedding_provider()
    if provider is None:
        logger.info(
            "No embedding provider configured — document %s chunks stored without "
            "embeddings; retrieval will use keyword fallback.",
            document.id,
        )
        return 0

    chunks = list(document.chunks.order_by("chunk_index"))
    vectors = provider.embed([chunk.content for chunk in chunks])
    if vectors is None:
        logger.warning(
            "Embedding call failed for document %s — chunks left unembedded.", document.id
        )
        return 0

    from .providers import OpenAIEmbeddingProvider

    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding = vector
        chunk.embedding_model = OpenAIEmbeddingProvider.MODEL
    KnowledgeChunk.objects.bulk_update(chunks, ["embedding", "embedding_model"])
    return len(vectors)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    strict=True so a dimension mismatch raises rather than silently zips
    to the shorter vector and returns a meaningless score. Callers catch
    ValueError per-chunk rather than letting one stale-model chunk (see
    KnowledgeChunk.embedding_model) crash the whole retrieval.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _keyword_overlap_score(query_words: set, content: str) -> int:
    content_words = set(re.findall(r"\w+", content.lower()))
    return len(query_words & content_words)


def retrieve_relevant_chunks(
    business, query: str, top_k: int = DEFAULT_TOP_K
) -> list[KnowledgeChunk]:
    """
    Returns up to `top_k` chunks from `business`'s READY documents, most
    relevant to `query` first.

    Prefers real cosine-similarity ranking over embedded chunks; if no
    embedding provider is configured (or a chunk was never embedded — see
    `_embed_chunks`), falls back to a plain keyword-overlap score across
    all chunks instead of returning nothing. Neither Anthropic's chat
    completion API nor a missing OpenAI key should mean a business's
    knowledge base is silently unused.
    """
    chunks = list(
        KnowledgeChunk.objects.filter(
            document__business=business, document__status=KnowledgeDocument.Status.READY
        ).select_related("document")
    )
    if not chunks:
        return []

    embedded = [c for c in chunks if c.embedding]
    provider = get_embedding_provider() if embedded else None
    if provider is not None:
        query_vectors = provider.embed([query])
        if query_vectors:
            query_vector = query_vectors[0]
            scored = []
            for chunk in embedded:
                try:
                    scored.append((chunk, _cosine_similarity(query_vector, chunk.embedding)))
                except ValueError:
                    # Dimension mismatch — chunk was embedded with a since-
                    # changed model. Skip it rather than crash retrieval.
                    logger.warning(
                        "Skipping chunk %s: embedding dimension mismatch (model=%s).",
                        chunk.id,
                        chunk.embedding_model,
                    )
            scored.sort(key=lambda pair: pair[1], reverse=True)
            top = [c for c, score in scored[:top_k] if score > 0]
            if top:
                return top

    query_words = set(re.findall(r"\w+", query.lower()))
    scored = [(c, _keyword_overlap_score(query_words, c.content)) for c in chunks]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [c for c, score in scored[:top_k] if score > 0]


def build_context_block(chunks: list[KnowledgeChunk]) -> str:
    """Formats retrieved chunks as a labelled block to append to the AI's system prompt."""
    if not chunks:
        return ""
    parts = [f"- {chunk.content.strip()}" for chunk in chunks]
    return "Relevant information from this business's knowledge base:\n" + "\n".join(parts)
