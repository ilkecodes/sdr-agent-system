## Quick orientation for AI coding agents

This repository is a small local RAG (retrieval-augmented generation) demo. Below are the focused facts and patterns that make edits and feature work low-friction.

1) Big picture
-- Postgres (pgvector) stores text chunks and embeddings (see `docker-compose.yml` and `sql/init.sql`). The table is `rag_chunks` with a JSONB `metadata` and a 384-dimension `vector` column.
-- Local embeddings use SentenceTransformers (model: `all-MiniLM-L6-v2`) and are stored as 384-d vectors (see `requirements.txt` and `sql/init.sql`).
- LLM calls are made to a local Ollama instance via the `ollama` Python client (`LLM_MODEL` set in `app/query.py` / `app/ingest.py`).

2) Important files to inspect (source of truth)
- `docker-compose.yml` — runs `pgvector/pgvector:pg15`; DB exposed on host port 5433 and mounts `./sql` for initialization.
-- `sql/init.sql` — table schema for `rag_chunks`, HNSW index, and vector dimension (384).
- `app/query.py` — interactive and CLI query logic: embeds a question, finds nearest chunks, then calls Ollama.
- `app/manage.py` — document management utilities: list, info, delete, stats, search.
-- `app/ingest.py` — contains embedding / query functions; note: there is no obvious full ingestion pipeline here (chunking/ingestion may be external or missing). If adding ingestion, follow the `metadata` keys used in `manage.py` (`filename`, `source`, `path`, `ingested_at`) and write `embedding` vectors with dim 384.

3) Developer workflows and commands (explicit examples)
- Start DB (creates DB and loads `sql/init.sql`):
  docker-compose up -d
- Typical DATABASE_URL used for local testing:
  postgresql+psycopg://rag:ragpw@localhost:5433/ragdb
  (export it in a `.env` file or shell before running scripts; scripts assert `DATABASE_URL`)
- List documents:
  python app/manage.py list
- Run interactive query:
  python app/query.py
- Run one-off query from CLI:
  python app/query.py "Who wrote the document?"

4) Project-specific conventions & patterns
-- Embeddings: code expects 384-dim vectors (matches local `all-MiniLM-L6-v2` SentenceTransformer). Keep this consistent when producing embeddings.
- Metadata JSON shape: code reads `metadata->>'filename'`, `metadata->>'source'`, and `metadata->>'ingested_at'` (epoch seconds). When ingesting, set these keys for compatibility.
- Vector searches use L2 (`vector_l2_ops`) and an HNSW index is created in `init.sql` — prefer L2 searches and the `embedding <-> :query_embedding` syntax used in `app/*`.
- Local models: SentenceTransformers (downloads on first run) and Ollama for LLMs. Calls to Ollama use `ollama.chat(model=LLM_MODEL, ...)`.
- Scripts require `DATABASE_URL` environment variable; load via `.env` using `python-dotenv`.

5) Integration points and external dependencies to be aware of
- PostgreSQL with pgvector extension (image `pgvector/pgvector:pg15`) — ensure Docker is available on the developer machine.
- Ollama (local LLM runtime) — the code assumes Ollama is reachable locally via the `ollama` Python client.
- sentence-transformers (and its backend like PyTorch) may download model weights at runtime.

6) Typical pitfalls to avoid
- Do not change the vector dimension in SQL without updating embedding generation code (`MODEL`/embedding size).
- Scripts assert `DATABASE_URL` — if you see assertion failures, ensure your `.env` or shell exports the URL.
-- There is no robust ingestion pipeline here; adding one should write `metadata` keys shown above and populate `embedding` with 384 floats.

7) If you modify storage/query behavior
- Keep SQL access patterns stable: the code uses parameterized queries with `sqlalchemy.text(...)` and expects `embedding <-> :query_embedding` and `LIMIT :top_k` semantics.

Files worth editing when extending functionality: `app/ingest.py` (ingest + embed), `app/manage.py` (admin ops), `app/query.py` (prompting / LLM usage), and `sql/init.sql` (schema changes).

If any of the above is unclear or you'd like the instructions to include additional examples (e.g., an ingestion snippet, sample `.env`), tell me which areas to expand.
