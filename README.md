# RAG-min — Knowledge Base-Powered RAG + SDR Agent System

**🌟 Your Knowledge Base is the Star**

This repository provides a production-ready system where your documentation powers intelligent sales outreach:

- **RAG Pipeline** — Convert documents (PDF/DOCX/web) into searchable knowledge base with vector embeddings
- **SDR Agent System** — Autonomous agent that uses your knowledge base for accurate, personalized prospect outreach

## Why This Matters

**Traditional SDR tools:** Generic AI that makes up features and hallucinates  
**This system:** Every message grounded in YOUR product docs, case studies, and knowledge base

✅ Auto-ingests prospect company data into knowledge base  
✅ Searches KB before drafting every email  
✅ Cites specific product benefits from your docs  
✅ Answers prospect questions using RAG (no hallucinations)  
✅ Traceable sources for compliance and accuracy

**Architecture:** Your Docs → Knowledge Base (pgvector) → RAG Search → Personalized Outreach

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

- `app/sdr_agent.py` — autonomous SDR agent with knowledge base integration
- `app/crm.py` — prospect/lead CRM with interaction tracking
- `app/tools.py` — KB search, research, enrichment, and outreach tools
- `app/gemini_rag.py` — 🆕 Gemini File API integration (optional multimodal RAG)
- `app/lead_finder.py` — import leads from CSV, LinkedIn search (mock)
- `sql/prospects.sql` — CRM schema for prospects, interactions, campaigns
- `examples/sdr_workflow.py` — complete demo workflow

### 🆕 CRM & Knowledge Base Integrations

- `app/typeform_integration.py` — **OAuth 2.0 + auto-ingest form responses to KB**
- `app/hubspot_integration.py` — **OAuth 2.0 + contact sync + call logging**
- `app/salesforce_integration.py` — **OAuth 2.0 + lead/contact sync + activity logging**
- `app/campaign_manager.py` — **Campaign triggers + automated prospect importing**
- `app/admin_ui.py` — **Web UI for uploads, OAuth, and campaign management**
- `sql/integrations.sql` — Integration schema (OAuth tokens, CRM sync, campaigns)
- `examples/integration_workflow.py` — Complete integration examples

### 🆕 Calendar Integrations

- `app/google_calendar_integration.py` — **OAuth 2.0 + real-time availability + meeting booking**
- `app/outlook_calendar_integration.py` — **OAuth 2.0 + Microsoft Graph + meeting booking**
- `app/calendar_manager.py` — **Unified calendar interface (provider-agnostic)**
- `examples/calendar_workflow.py` — Calendar integration examples

📖 See [`docs/KNOWLEDGE_BASE_INTEGRATION.md`](docs/KNOWLEDGE_BASE_INTEGRATION.md) for how KB powers SDR.  
📖 See [`docs/GEMINI_INTEGRATION.md`](docs/GEMINI_INTEGRATION.md) for Gemini File API setup.  
📖 See [`docs/SDR_AGENT.md`](docs/SDR_AGENT.md) for full SDR agent documentation.  
📖 See [`docs/CRM_INTEGRATIONS.md`](docs/CRM_INTEGRATIONS.md) for **CRM integration guide**.  
📖 See [`docs/CALENDAR_INTEGRATIONS.md`](docs/CALENDAR_INTEGRATIONS.md) for **Calendar integration guide**.

---

## Quick Start

### Option A: RAG Only

```bash
# 1. Start database
docker compose up -d

# 2. Setup environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Run pipeline (convert + ingest + query)
export DATABASE_URL='postgresql+psycopg://rag:ragpw@localhost:5433/ragdb'
python -m app.pipeline data/sample.txt --out out --ingest --db "$DATABASE_URL" --query --question "Summarize the document"
```

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
psql $DATABASE_URL -f sql/integrations.sql  # For CRM integrations

# 4. Run demo workflow (imports 3 leads, researches, drafts outreach)
python examples/sdr_workflow.py

# 5. Interactive chat with agent
python examples/sdr_workflow.py --chat
```

### Option C: 🆕 Admin UI + CRM Integrations

```bash
# 1. Follow Option B steps 1-3 above

# 2. Set integration environment variables
export TYPEFORM_CLIENT_ID=your_typeform_client_id
export TYPEFORM_CLIENT_SECRET=your_typeform_secret
export HUBSPOT_CLIENT_ID=your_hubspot_client_id
export HUBSPOT_CLIENT_SECRET=your_hubspot_secret
export SALESFORCE_CLIENT_ID=your_salesforce_client_id
export SALESFORCE_CLIENT_SECRET=your_salesforce_secret
export GOOGLE_CLIENT_ID=your_google_client_id
export GOOGLE_CLIENT_SECRET=your_google_secret
export OUTLOOK_CLIENT_ID=your_outlook_client_id
export OUTLOOK_CLIENT_SECRET=your_outlook_secret
export FLASK_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')

# 3. Start Admin UI
python app/admin_ui.py
# Visit http://localhost:8000 for:
# - Document uploads to knowledge base
# - OAuth setup (Typeform, HubSpot, Salesforce, Google/Outlook Calendar)
# - Campaign management with CRM triggers
# - Calendar availability checking and meeting booking
```

📖 See [`docs/CRM_INTEGRATIONS.md`](docs/CRM_INTEGRATIONS.md) for complete integration setup.  
📖 See [`docs/SDR_AGENT.md`](docs/SDR_AGENT.md) for complete agent guide.

---

## Technical Details

### Embedding Dimension

`sql/init.sql` creates a `vector(384)` column to match the default local model (`all-MiniLM-L6-v2`) which produces 384-d embeddings. If you switch to a 1536-d provider (e.g., OpenAI `text-embedding-3-small`), update the schema and re-ingest vectors.

### Memory Integration

The pipeline is agnostic to memory stores. You can integrate with Letta or other memory agents by reading/writing to `rag_chunks` or using it as an additional session memory store.

### CI and Integration Tests

A GitHub Actions workflow [`.github/workflows/integration.yml`](.github/workflows/integration.yml) runs integration tests on a self-hosted runner (requires Docker).

---

## Documentation

- [`docs/KNOWLEDGE_BASE_INTEGRATION.md`](docs/KNOWLEDGE_BASE_INTEGRATION.md) — How KB powers SDR operations
- [`docs/SDR_AGENT.md`](docs/SDR_AGENT.md) — Complete SDR agent guide
- [`docs/CRM_INTEGRATIONS.md`](docs/CRM_INTEGRATIONS.md) — **🆕 Typeform/HubSpot/Salesforce integration guide**
- [`docs/CALENDAR_INTEGRATIONS.md`](docs/CALENDAR_INTEGRATIONS.md) — **🆕 Google/Outlook Calendar integration guide**
- [`docs/GEMINI_INTEGRATION.md`](docs/GEMINI_INTEGRATION.md) — Gemini File API setup and usage
- [`docs/BUILDING_YOUR_KB.md`](docs/BUILDING_YOUR_KB.md) — Step-by-step knowledge base setup
- [`docs/GEMINI_IMPLEMENTATION.md`](docs/GEMINI_IMPLEMENTATION.md) — Implementation summary

---

## Next Steps

- **Add more knowledge:** Ingest your product docs, case studies, FAQs
- **Configure agents:** Customize outreach templates and research depth
- **🆕 Connect CRMs:** Set up Typeform, HubSpot, or Salesforce integrations
- **🆕 Connect calendars:** Set up Google Calendar or Outlook Calendar for automated meeting booking
- **🆕 Create campaigns:** Build automated prospect import campaigns with triggers
- **Integrate Gemini:** Enable multimodal RAG for PDFs with images
- **Production deployment:** Add secret redaction, monitoring, and rate limiting

---

## License

MIT
