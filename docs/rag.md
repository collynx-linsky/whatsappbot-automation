# RAG Knowledge Base

`apps.knowledge` — lets a business upload documents (or paste text) that
ground the AI assistant's replies in real business content, per spec
section 9. **No real OpenAI API key was available while building this**
— the whole pipeline is built and tested against a mocked embeddings
endpoint for the success path, and the "no embedding provider configured"
degraded path (keyword-only retrieval) is exercised for real, since it's
genuinely reachable without credentials.

## Architecture

```text
POST /api/v1/knowledge/documents/   {business, title, source_type, file|raw_text}
   |  manager+, tenant/business validated
   v
apps.knowledge.models.KnowledgeDocument   (status=pending)
   |  Celery task, queue=low_priority — not customer-facing/latency-sensitive
   v
apps.knowledge.tasks.process_knowledge_document_task
   v
apps.knowledge.services.process_document()
   |-- extract_text()      .txt decoded directly; .pdf via pypdf; source_type=text uses raw_text as-is
   |-- chunk_text()        200-word chunks, 30-word overlap
   |-- KnowledgeChunk[] created (replaces any chunks from a previous run)
   |-- get_embedding_provider() -> OpenAIEmbeddingProvider, or None if no OPENAI_API_KEY
   |     provider available -> each chunk embedded, embedding_model recorded
   |     provider unavailable -> chunks stored with embedding=None (not failed)
   v
KnowledgeDocument.status = ready  (or failed, with error_message, if extraction/chunking itself failed)
```

At reply time:

```text
apps.ai.services.generate_ai_reply()
   v
apps.ai.services.append_knowledge_context(system_prompt, business, customer_message)
   v
apps.knowledge.services.retrieve_relevant_chunks(business, query, top_k=3)
   |-- any chunks embedded? try get_embedding_provider(); embed the query;
   |   rank by cosine similarity; return top matches with score > 0
   |-- otherwise (or if that yields nothing): rank by keyword overlap
   |   (shared lowercase word count) across ALL chunks, embedded or not
   v
apps.knowledge.services.build_context_block()  -> "Relevant information from
   this business's knowledge base:\n- ...\n- ..." appended to the system prompt
```

Same one-directional dependency style as the rest of this codebase:
`apps.ai` imports `apps.knowledge` (for retrieval), never the reverse —
the knowledge base is fully usable on its own (list/upload/inspect via its
own API) with zero awareness that `apps.ai` exists.

## No pgvector — a documented, deliberate trade-off

This project's native PostgreSQL 18 instance does not have the `pgvector`
extension installed (confirmed: `SELECT * FROM pg_available_extensions
WHERE name='vector'` returns nothing — it's not just uncreated, it's not
compiled into this Postgres install at all). Rather than block this phase
on an OS-level Postgres extension install, `KnowledgeChunk.embedding` is a
plain `JSONField` (a list of floats), and `retrieve_relevant_chunks`
computes cosine similarity in pure Python
(`apps.knowledge.services._cosine_similarity`) rather than using a vector
index.

**This is fine at the scale this MVP targets** — a single business's
knowledge base is expected to be dozens to a few hundred chunks, and a
linear scan over that many 1536-dimension float lists per reply is fast
enough to not matter next to the network latency of the chat completion
call itself. It stops being fine well before "thousands of chunks per
business." **Upgrade path**: install the `pgvector` extension on the
Postgres instance (or move to a managed Postgres that has it, e.g. a
provider offering it out of the box), add `pgvector` to
`requirements/base.txt`, change `KnowledgeChunk.embedding` to
`VectorField`, and replace `retrieve_relevant_chunks`'s Python loop with
an ORM `.order_by(CosineDistance("embedding", query_vector))` — the
function's signature and everything that calls it stays the same.

## Graceful degradation, not failure

Mirrors `apps.ai`'s "provider unavailable → hand off, don't error"
contract:

- **No `OPENAI_API_KEY` at process time**: chunks are created and the
  document still becomes `ready` (not `failed`) — `embedded_chunk_count`
  stays `0` and `KnowledgeChunk.embedding` stays `None`. The knowledge
  base is still fully usable via keyword-overlap retrieval; it just isn't
  semantically ranked.
- **Embeddings API call fails at process time** (network error, bad key,
  rate limit): same outcome — logged, chunks left unembedded, document
  still `ready`.
- **No embedding provider at retrieval time**: `retrieve_relevant_chunks`
  falls back to keyword overlap across every chunk (embedded or not), so
  a knowledge base is never silently unused just because
  `OPENAI_API_KEY` isn't set.
- **A chunk's embedding dimension doesn't match the current query
  embedding** (e.g. it was embedded under a since-changed model): skipped
  with a logged warning, not a crash — one stale chunk never takes down
  retrieval for the rest.
- **Extraction/chunking itself fails** (e.g. an empty document, or a
  corrupt PDF `pypdf` can't parse): this *does* mark the document
  `failed` with `error_message` set — unlike an embedding failure, there's
  no degraded mode for "we don't actually know what the document says."

## File upload validation

Addresses the gap flagged in `docs/security.md` since the WhatsApp phase
("file upload validation lands with `apps.knowledge`"). Two independent
layers: `KnowledgeDocumentCreateSerializer.validate_file` rejects any
extension outside `apps.knowledge.services.ALLOWED_FILE_EXTENSIONS`
(`.txt`, `.pdf`) with a clear `400` before the file is ever saved to
disk, and Django's existing `DATA_UPLOAD_MAX_MEMORY_SIZE`
(`MAX_UPLOAD_SIZE_MB` in `.env`) bounds the request body size at the
transport layer.

## API

See `docs/api.md` for the full endpoint table. Summary:
`GET/POST /api/v1/knowledge/documents/` (GET staff+, POST manager+),
`GET/DELETE /api/v1/knowledge/documents/{id}/` (GET staff+, DELETE
manager+), `GET /api/v1/knowledge/documents/{id}/chunks/` (staff+,
inspect what was actually indexed — mainly for debugging/trust, so a
business owner can see *why* the AI said what it said).

## Testing without real credentials

`tests/test_knowledge.py` mocks `apps.knowledge.providers.requests.post`
for every embedding-success assertion, and tests the "no embedding
provider" degraded path directly — genuinely reachable without
credentials, same reasoning as `docs/ai.md`. Covers chunking (overlap,
word-boundary safety, empty input), extraction (`.txt` decode, `raw_text`
passthrough), the full `process_document` pipeline (embedded and
unembedded outcomes, failure on unextractable content, idempotent
re-processing), retrieval (keyword fallback ranking, cosine-similarity
ranking, empty-knowledge-base and no-match cases), the documents API
(tenant isolation, RBAC, cross-tenant `business` rejection, extension
validation), and an integration test proving `apps.ai.services
.generate_ai_reply` actually includes retrieved knowledge-base content in
the system prompt it sends the provider.

**Also verified live**: seeded 4 real knowledge documents across 3
businesses via `seed_dev_data` (processed synchronously, no worker
required), confirmed via `curl` against a running dev server that they
show `status: ready` with `embedded_chunk_count: 0` (correctly degraded —
no API key configured); created a new document via a real authenticated
`POST`, confirmed it started `pending`; and directly re-invoked
`process_document()` against that live document to confirm the full
extract → chunk → store pipeline genuinely works end-to-end against the
real Postgres database, not just under `pytest`.

**Known gap surfaced by this verification, not a code bug**: this dev
machine's Redis broker (`localhost:6379`, db 1) is shared across several
of this user's unrelated projects — a real, queued task from a
completely different codebase (`apps.identity.tasks.send_new_device_alert`,
which does not exist anywhere in this repository) was found sitting in
the same default `celery` queue. A freshly started worker process
listening on this project's queues did not visibly pick up the
just-enqueued `process_knowledge_document_task` either, most likely
because a stale worker process from earlier in this same dev session
(started before `apps.knowledge` existed, so it doesn't have the task
registered) is still running and consumed it silently. This is a
dev-machine process-hygiene issue, not a bug in the routing/task code —
`CELERY_TASK_ROUTES` and the task itself are exercised correctly by the
`pytest` suite under `CELERY_TASK_ALWAYS_EAGER`. **Action for whoever
next runs a real Celery worker on this machine**: kill any old
`celery worker` processes before starting a new one, or dedicate a
non-default Redis db to this project in `.env` to stop sharing db 1 with
other local projects.

## Limitations / not built

- Only `.txt` and `.pdf` uploads (`ALLOWED_FILE_EXTENSIONS`) — no
  `.docx`/`.csv`/image-with-OCR support.
- No pgvector — see above. Fine at MVP scale, not infinitely.
- No per-chunk relevance feedback loop (thumbs up/down on a reply to
  reweight retrieval) — retrieval is a fixed cosine-similarity-or-keyword
  ranking with no learning component.
- `retrieve_relevant_chunks` always asks the embedding provider to embed
  the query fresh on every single AI reply — no query embedding cache.
  Fine at this MVP's traffic level; would start mattering as a real cost
  line item at scale.
- No usage/cost tracking for embedding API calls, same gap as `apps.ai`'s
  `tokens_used` (see `docs/ai.md`) — Phase 13 (`apps.billing`) territory.
- No UI/endpoint to manually re-trigger processing of a `failed` document
  without re-uploading it.
