# SDR Agent System

**Knowledge Base-Powered Autonomous Sales Development Representative**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-14+-blue.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Transform your sales development process with an AI agent that researches prospects, qualifies leads, and drafts personalized outreach—all grounded in your actual product documentation.

---

## 🌟 What Makes This Special

**Your Knowledge Base is the Star**

Unlike generic AI tools that hallucinate features, this SDR agent:
- ✅ Grounds all outreach in **your actual product documentation**
- ✅ Automatically ingests prospect company data into knowledge base
- ✅ Cites specific features, case studies, and benefits from your docs
- ✅ Never makes up product capabilities
- ✅ Provides traceable sources for compliance and accuracy

**Architecture:**
```
Your Docs → Knowledge Base (pgvector) → RAG Search → Personalized Outreach
     ↓              ↑                        ↓
   Ingest      Auto-research            LLM + Context
             (company websites)       (accurate, cited)
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker (for PostgreSQL + pgvector)
- Ollama (for local LLM)

### One-Command Setup
```bash
./setup_sdr.sh
```

This will:
1. ✅ Start PostgreSQL + pgvector in Docker
2. ✅ Create virtual environment
3. ✅ Install dependencies
4. ✅ Set up database schemas (RAG + CRM)
5. ✅ Download Ollama model
6. ✅ Create `.env` file

### Run the Demo
```bash
python examples/sdr_workflow.py
```

---

## 🎯 Core Capabilities

### 1. **Knowledge Base Intelligence** 🧠
Three RAG modes:
- **Local RAG** (default): 100% private, free, works offline
- **Gemini RAG** (optional): Multimodal (PDFs, images, code), with citations
- **Hybrid Mode**: Combines both for maximum accuracy

### 2. **Lead Management CRM** 📊
- Complete prospect database with lifecycle stages
- Interaction logging (emails, LinkedIn, calls, meetings)
- Conversation memory for multi-turn dialogues
- Lead scoring against Ideal Customer Profile (ICP)

### 3. **Automated Research & Enrichment** 🔍
- Company research (scrapes websites → auto-ingests to KB)
- LinkedIn enrichment (profile data extraction)
- Tech stack detection (identifies CRM, infrastructure, tools)
- News monitoring (funding, product launches, hiring)

### 4. **Intelligent Qualification** 🎓
- ICP scoring algorithm (0-1 based on company size, industry, job title, tech stack)
- Automatic stage progression
- Qualification reasoning ("Why this prospect is/isn't a good fit")

### 5. **AI-Powered Personalization** ✍️
- Searches knowledge base before every draft
- LLM-generated emails citing specific product benefits
- Multi-channel support (Email, LinkedIn, call scripts)
- Citation tracking (shows which KB sources were used)

### 6. **Outreach Automation** 📧
- SMTP email sending with dry-run mode
- LinkedIn automation (integration-ready)
- Follow-up scheduling with automatic reminders
- Full workflow: Research → Qualify → Draft → Send → Track

### 7. **Interactive Chat Interface** 💬
- Tool-calling agent (dynamically invokes research, qualification, drafting)
- Conversation memory
- Coaching mode (answers questions about prospects, strategies, objections)

---

## 📖 Usage Examples

### Import Leads
```bash
python -m app.lead_finder import-csv data/leads.csv
```

### Run Full Workflow
```bash
python -m app.sdr_agent --workflow --prospect-id 1 --dry-run
```

### Interactive Chat
```bash
python -m app.sdr_agent --chat
```

### Build Knowledge Base
```bash
# Ingest product documentation
python -m app.ingest docs/

# Parse company websites
python -m app.web_parse https://yourcompany.com/about --db $DATABASE_URL
```

### Python API
```python
from app.sdr_agent import SDRAgent
from app.crm import create_prospect

# Create prospect
prospect_id = create_prospect(
    email="john@example.com",
    first_name="John",
    company_name="Example Inc",
    job_title="VP of Sales"
)

# Run full workflow
agent = SDRAgent()
result = agent.run_full_workflow(
    prospect_id=prospect_id,
    channel="email",
    dry_run=True  # Review before sending
)
```

---

## 🏗️ Architecture

### Tech Stack
- **Python 3.11+** with SQLAlchemy
- **PostgreSQL + pgvector** (384-d vectors)
- **Local Embeddings**: SentenceTransformers (all-MiniLM-L6-v2)
- **Local LLM**: Ollama (llama3.2)
- **Optional**: Google Gemini API (multimodal RAG)
- **Web Parsing**: Readability + Markdownify

### Project Structure
```
rag-min/
├── app/
│   ├── sdr_agent.py          # Autonomous agent with tool-calling
│   ├── crm.py                # Prospect/interaction management
│   ├── tools.py              # 12+ research/enrichment/outreach tools
│   ├── gemini_rag.py         # Gemini File API integration
│   ├── lead_finder.py        # CSV import and lead discovery
│   ├── query.py              # RAG query engine
│   ├── ingest.py             # Document ingestion
│   ├── web_parse.py          # Web scraping → KB
│   └── convert.py            # Document conversion
├── sql/
│   ├── init.sql              # RAG chunks schema
│   └── prospects.sql         # CRM schema
├── examples/
│   ├── sdr_workflow.py       # Complete demo
│   ├── kb_powered_demo.py    # Knowledge base in action
│   └── gemini_demo.py        # Gemini API demo
├── docs/
│   ├── SDR_AGENT.md          # Complete documentation
│   ├── KNOWLEDGE_BASE_INTEGRATION.md
│   ├── BUILDING_YOUR_KB.md
│   └── GEMINI_INTEGRATION.md
└── setup_sdr.sh              # One-command setup
```

---

## 🎨 Real-World Scenario

**Input:** 100 leads from CSV

**Agent does:**
1. **Import** → Creates 100 prospects in CRM
2. **Research** → Enriches each (LinkedIn, website, tech stack) → adds to KB
3. **Qualify** → Scores against ICP → 30 are "high fit"
4. **Draft** → Generates 30 personalized emails using KB context
5. **Review** → You preview all 30 drafts (dry-run mode)
6. **Send** → Sends approved emails via SMTP
7. **Track** → Logs all interactions, sets follow-up dates
8. **Follow-up** → Auto-generates follow-ups for non-responders

**Time:** ~1 hour automated vs 20+ hours manual  
**Quality:** Every email cites specific product benefits from your docs

---

## 📚 Documentation

- [**SDR Agent Guide**](docs/SDR_AGENT.md) - Complete feature documentation
- [**Knowledge Base Integration**](docs/KNOWLEDGE_BASE_INTEGRATION.md) - How KB powers the system
- [**Building Your KB**](docs/BUILDING_YOUR_KB.md) - Step-by-step setup guide
- [**Gemini Integration**](docs/GEMINI_INTEGRATION.md) - Multimodal RAG setup
- [**Implementation Summary**](docs/IMPLEMENTATION_SUMMARY.md) - Technical details

---

## ✅ Production-Ready Features

- **Safety**: Dry-run mode, email preview, robots.txt compliance, PII detection
- **Scalability**: Database-backed, async-ready, batch operations, connection pooling
- **Observability**: Full interaction logging, audit trails, error tracking, KB attribution
- **Compliance**: GDPR considerations, CAN-SPAM guidelines, consent tracking

---

## 🔌 Integration Points

### Built-in (Working Now)
- ✅ PostgreSQL + pgvector (knowledge base)
- ✅ Ollama LLM (local, private)
- ✅ SentenceTransformers (local embeddings)
- ✅ Web parsing (Readability + Markdown)
- ✅ SMTP email sending

### Ready for Integration (Mock → Real)
- 🔌 LinkedIn Sales Navigator API
- 🔌 Apollo.io / ZoomInfo (enrichment)
- 🔌 Clearbit / Hunter.io (company data)
- 🔌 BuiltWith / Wappalyzer (tech stack)
- 🔌 NewsAPI / Crunchbase (signals)
- 🔌 Salesforce / HubSpot (CRM sync)
- 🔌 Calendly (meeting scheduling)
- 🔌 Gemini File API (multimodal RAG)

---

## 💰 Cost Comparison

### Local RAG (Default)
- Setup: **Free**
- Storage: **Free** (self-hosted)
- Queries: **Free** (unlimited)
- **Total: $0/month**

### With Gemini (Optional)
- Indexing: $0.15/1M tokens (one-time)
- Storage: **Free**
- Query embeddings: **Free**
- LLM generation: ~$0.001/query
- **Total: ~$1-5/month for typical usage**

---

## 🚀 Roadmap

- [ ] Real-time email response monitoring
- [ ] Advanced conversation memory (Letta/MemGPT)
- [ ] Task queue (Celery/RQ) for high-volume workflows
- [ ] A/B testing framework for messages
- [ ] Salesforce/HubSpot native integrations
- [ ] Multi-agent collaboration
- [ ] Intent signal detection
- [ ] Account-based plays

---

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🙏 Acknowledgments

- Built on top of [pgvector](https://github.com/pgvector/pgvector)
- Uses [SentenceTransformers](https://www.sbert.net/) for embeddings
- Powered by [Ollama](https://ollama.ai/) for local LLM
- Optional [Gemini API](https://ai.google.dev/gemini-api) integration

---

## 📧 Contact

Questions? Open an issue or reach out!

---

**⭐ Star this repo if you find it useful!**
