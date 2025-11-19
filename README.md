# RAG-min — Knowledge Base-Powered RAG + SDR Agent System

**🌟 Your Knowledge Base is the Star**

This repository provides a production-ready system where **your documentation powers intelligent sales outreach**:

1. **RAG Pipeline** - Convert documents (PDF/DOCX/web) into searchable knowledge base with vector embeddings
2. **SDR Agent System** - Autonomous agent that uses your knowledge base for accurate, personalized prospect outreach

## Why This Matters

**Traditional SDR tools:** Generic AI that makes up features and hallucinations  
**This system:** Every message grounded in YOUR product docs, case studies, and knowledge base

- ✅ Auto-ingests prospect company data into knowledge base
- ✅ Searches KB before drafting every email
- ✅ Cites specific product benefits from your docs
- ✅ Answers prospect questions using RAG (no hallucinations)
- ✅ Traceable sources for compliance and accuracy

**Architecture:** `Your Docs → Knowledge Base (pgvector) → RAG Search → Personalized Outreach`

---

## What's Included

### RAG Components (The Foundation 🌟)
- `app/convert.py` — convert source files (pdf, docx, pptx, xlsx/csv, json, html, txt) into canonical Markdown and chunk JSONL
- `app/ingest_snippet.py` — ingest chunk JSONL into `rag_chunks` with embeddings (sentence-transformers by default)
- `app/query.py` — semantic search + LLM query flow using Ollama
- `app/web_parse.py` — fetch and parse web pages into knowledge base
- `app/pipeline.py` — orchestration: convert → ingest → query
- `sql/init.sql` — DB schema for `rag_chunks` with HNSW index (384-d vectors)

### SDR Agent Components (KB-Powered ⭐)
- `app/sdr_agent.py` — autonomous SDR agent with **knowledge base integration**
- `app/crm.py` — prospect/lead CRM with interaction tracking
- `app/tools.py` — **KB search, research, enrichment, and outreach tools**
- `app/gemini_rag.py` — **🆕 Gemini File API integration (optional multimodal RAG)**
- `app/lead_finder.py` — import leads from CSV, LinkedIn search (mock)
- `sql/prospects.sql` — CRM schema for prospects, interactions, campaigns
- `examples/sdr_workflow.py` — complete demo workflow

**See [docs/KNOWLEDGE_BASE_INTEGRATION.md](docs/KNOWLEDGE_BASE_INTEGRATION.md) for how KB powers SDR.**  
**See [docs/GEMINI_INTEGRATION.md](docs/GEMINI_INTEGRATION.md) for Gemini File API setup.**  
**See [docs/SDR_AGENT.md](docs/SDR_AGENT.md) for full SDR agent documentation.**

## Quick Start

### Option A: RAG Only

### Option B: SDR Agent System

```bash
# 1. Start database
docker compose up -d

# 2. Setup environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Create CRM tables
export DATABASE_URL='postgresql+psycopg://rag:ragpw@localhost:5433/ragdb'
psql $DATABASE_URL -f sql/prospects.sql

# 4. Run demo workflow (imports 3 leads, researches, drafts outreach)
python examples/sdr_workflow.py

# 5. Interactive chat with agent
python examples/sdr_workflow.py --chat
```

See **[docs/SDR_AGENT.md](docs/SDR_AGENT.md)** for complete guide.

---

## RAG Pipeline (Original Functionality)

### Setup

1) Create a venv and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install sentence-transformers pandas pypdf pgvector
```

2) Start the DB

```bash
docker compose up -d
```

3) Run the pipeline (convert + ingest + query)

```bash
# export DATABASE_URL if not set
export DATABASE_URL='postgresql+psycopg://rag:ragpw@localhost:5433/ragdb'

# Convert + ingest + run a sample query
python -m app.pipeline path/to/doc.pdf --out out --ingest --db "$DATABASE_URL" --query --question "Summarize the document"
```

Notes and decisions
 - Embedding dimension: `sql/init.sql` currently creates a `vector(384)` column to match the default local model (`all-MiniLM-L6-v2`) which produces 384-d embeddings. If you later switch to a 1536-d provider (e.g., OpenAI `text-embedding-3-small`), update the schema and re-ingest vectors.

- Memory: you mentioned using `letta` for memory — the pipeline is agnostic to the memory store; you can replace the embedding store or add a separate memory agent that reads/writes to Lett a. Document how Lett a integrates with `rag_chunks` or use it as an additional store for session memory.

CI and integration tests
- A GitHub Actions workflow `.github/workflows/integration.yml` was added to run integration tests on a self-hosted runner (requires Docker).

Next steps you might want
- Add `app/pipeline.py` integration into CI or create a dedicated image that bundles heavy deps (sentence-transformers) to speed CI.
- Implement secret redaction before ingestion and flag `secrets_found` in chunk metadata.
- Decide embedding dim (1536 vs 384) and standardize across ingestion and DB schema.

If you want, I can update the schema to `vector(384)` to match the current local embedding model and provide a migration helper.
