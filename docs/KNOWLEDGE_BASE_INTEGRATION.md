# 🌟 Knowledge Base: The Star of Your SDR System

## Overview

Your **RAG (Retrieval-Augmented Generation) knowledge base** is the foundational intelligence that powers personalized, accurate, and value-driven sales outreach. Every part of the SDR agent leverages your knowledge base to ensure prospects receive relevant, credible information.

---

## How the Knowledge Base Powers SDR Operations

### 1. **Company Research → Knowledge Base**

When researching a company, the agent automatically ingests their website into your knowledge base:

```python
from app.tools import LeadEnrichment

# Research company - automatically parses and ingests to KB
result = LeadEnrichment.research_company(
    domain="example.com",
    ingest_to_kb=True  # 🌟 Adds company info to knowledge base!
)

# Now you can query: "What does example.com do?"
# And get answers from your knowledge base
```

**What happens:**
1. Agent fetches company's `/about`, `/company`, or homepage
2. Uses your `web_parse.py` to extract clean markdown
3. Automatically chunks and embeds content using `convert.py` 
4. Stores in `rag_chunks` table with pgvector embeddings
5. Future queries can retrieve this context instantly

---

### 2. **Product Knowledge for Personalization**

Before drafting ANY outreach, the agent searches your knowledge base:

```python
# In draft_outreach():
kb_query = f"product benefits for {prospect['industry']} {prospect['job_title']}"
kb_results = KnowledgeBaseTools.search_knowledge(kb_query, top_k=3)

# LLM receives:
# - Prospect data (name, company, role)
# - 🌟 Relevant product docs from your KB
# - Case studies matching their industry
# - Specific features that solve their problems
```

**Example:**

Prospect: VP of Sales at 200-person SaaS company

Knowledge Base retrieves:
- Case study: "How we helped Acme SaaS increase pipeline by 40%"
- Feature doc: "Sales team collaboration features"
- Pricing: "Enterprise plan for 50-500 employees"

LLM drafts email citing **actual product benefits** from your docs, not hallucinations!

---

### 3. **Answering Prospect Questions**

When prospects reply with questions, agent uses full RAG pipeline:

```python
from app.tools import KnowledgeBaseTools

# Prospect asks: "Does your product integrate with Salesforce?"
response = KnowledgeBaseTools.answer_from_knowledge(
    question="Does our product integrate with Salesforce?",
    top_k=5
)

# Returns:
# {
#   "answer": "Yes, we have a native Salesforce integration that syncs...",
#   "sources": [
#     {"content_preview": "Salesforce Integration Guide...", "distance": 0.23},
#     {"content_preview": "API Documentation - CRM Sync...", "distance": 0.31}
#   ]
# }
```

**Benefits:**
- ✅ Answers are grounded in your documentation
- ✅ No hallucinations or made-up features
- ✅ Traceable sources for auditing
- ✅ Always up-to-date (just re-ingest docs when they change)

---

### 4. **Qualification with KB Context**

Agent can qualify leads based on knowledge base content:

```python
# Search KB for relevant use cases
kb_results = KnowledgeBaseTools.search_knowledge(
    query=f"customers in {prospect['industry']} industry",
    top_k=3
)

# If KB has case studies in their industry → higher qualification score
# If KB mentions their tech stack → signal of good fit
# If KB has content about their pain points → strong relevance
```

---

## Knowledge Base Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  Knowledge Base (PostgreSQL + pgvector)     │
│                                                              │
│  ┌────────────────┐         ┌─────────────────┐            │
│  │  rag_chunks    │         │   documents      │            │
│  │  - content     │         │   - title        │            │
│  │  - embedding   │◄────────┤   - markdown     │            │
│  │  - metadata    │         │   - metadata     │            │
│  └────────────────┘         └─────────────────┘            │
└─────────────────────────────────────────────────────────────┘
                    ▲                        ▲
                    │                        │
        ┌───────────┴────────────┬──────────┴───────────┐
        │                        │                      │
   ┌────────────┐         ┌──────────────┐      ┌──────────────┐
   │  Ingest    │         │  Web Parse   │      │  Query/RAG   │
   │  Pipeline  │         │  (Prospect   │      │  (Search &   │
   │            │         │   Research)  │      │   Answer)    │
   └────────────┘         └──────────────┘      └──────────────┘
         │                        │                      │
         │                        │                      │
         └────────────────────────┼──────────────────────┘
                                  │
                          ┌───────▼────────┐
                          │   SDR Agent    │
                          │   - Research   │
                          │   - Qualify    │
                          │   - Draft      │
                          │   - Outreach   │
                          └────────────────┘
```

### Key Components

1. **`query.py`** - RAG query engine
   - `embed_query()` - Convert text to 384-d vector
   - `search_similar_chunks()` - Find relevant docs by cosine similarity
   - `ask()` - Full RAG pipeline (search + LLM generation)

2. **`web_parse.py`** - Web content ingestion
   - Respects robots.txt
   - Extracts clean article content (readability)
   - Converts to markdown
   - Auto-chunks and embeds via `convert.py`

3. **`ingest.py` / `pipeline.py`** - Bulk document processing
   - Process PDFs, Word docs, HTML, markdown
   - Chunk intelligently (preserves context)
   - Generate embeddings locally (SentenceTransformers)

---

## Populating Your Knowledge Base

### 1. Add Product Documentation

```bash
# Ingest your product docs
python -m app.ingest docs/product_features.md
python -m app.ingest docs/pricing.pdf
python -m app.ingest docs/api_reference.html
```

### 2. Add Case Studies

```bash
# Ingest customer success stories
python -m app.ingest case_studies/acme_corp.md
python -m app.ingest case_studies/beta_inc.pdf
```

### 3. Research Prospects Automatically

```python
from app.lead_finder import LeadFinder
from app.tools import LeadEnrichment

# Import leads
finder = LeadFinder()
finder.import_from_csv("data/leads.csv")

# For each lead, research and ingest their company
for lead in leads:
    domain = lead['company_domain']
    
    # This automatically adds company info to KB!
    LeadEnrichment.research_company(
        domain=domain,
        ingest_to_kb=True
    )
```

### 4. Ingest from URLs

```bash
# Parse and ingest web pages
python -m app.web_parse https://example.com/about --db $DATABASE_URL
```

---

## Using Knowledge Base in Agent Workflows

### Tool 1: `search_knowledge`

Search for relevant documents without generating an answer.

```python
from app.tools import KnowledgeBaseTools

results = KnowledgeBaseTools.search_knowledge(
    query="enterprise pricing plans",
    top_k=5
)

# Returns:
# [
#   {
#     "rank": 1,
#     "content": "Enterprise Plan: Starting at $499/mo...",
#     "metadata": {"source_uri": "pricing.md"},
#     "distance": 0.23,
#     "relevance_score": 0.77
#   },
#   ...
# ]
```

### Tool 2: `answer_from_knowledge`

Get LLM-generated answer grounded in KB docs.

```python
response = KnowledgeBaseTools.answer_from_knowledge(
    question="What industries do we serve best?",
    top_k=5
)

# Returns:
# {
#   "answer": "We serve SaaS, FinTech, and Healthcare...",
#   "sources": [
#     {"content_preview": "Case Study: FinTech...", "distance": 0.19},
#     ...
#   ],
#   "question": "..."
# }
```

### Integrated into Agent

The SDR agent **automatically** uses these tools:

```python
from app.sdr_agent import SDRAgent

agent = SDRAgent()

# When you run workflow, agent:
# 1. Searches KB for product info relevant to prospect
# 2. Uses KB context in drafting personalized emails
# 3. Cites specific features/case studies from KB
# 4. Ensures accuracy (no hallucinations)

agent.run_full_workflow(
    prospect_id=1,
    channel="email",
    dry_run=True
)
```

**In the draft_outreach step:**
```
✍️  Drafting email outreach for: sarah@techcorp.com
  📚 Searching knowledge base...
  ✅ Found 3 relevant knowledge base sources
  ✅ Draft complete (using 3 KB sources)
```

---

## Best Practices

### 1. Keep Knowledge Base Fresh

```bash
# Regular updates
python -m app.ingest docs/  # Re-ingest documentation
python -m app.web_parse https://yourcompany.com/blog/latest-announcement
```

### 2. Organize with Metadata

```python
# When ingesting, add rich metadata
metadata = {
    "source_type": "case_study",
    "industry": "FinTech",
    "company_size": "201-500",
    "publish_date": "2024-11-15"
}

# Later filter searches
results = search_similar_chunks(query_embedding, top_k=10)
filtered = [r for r in results if r[1].get('industry') == 'FinTech']
```

### 3. Version Control Your Docs

Store source documents in git:
```
knowledge/
  ├── product/
  │   ├── features.md
  │   ├── pricing.md
  │   └── integrations.md
  ├── case_studies/
  │   ├── acme_corp.md
  │   └── beta_inc.md
  └── messaging/
      ├── value_props.md
      └── objection_handling.md
```

Re-ingest on updates:
```bash
python -m app.pipeline knowledge/
```

---

## Advanced: RAG-Powered Chat

Prospects can chat with agent backed by full knowledge base:

```python
from app.sdr_agent import SDRAgent

agent = SDRAgent()

# Interactive chat
agent.chat()

# Example conversation:
# User: "Tell me about your Salesforce integration"
# Agent: [searches KB] → [generates answer] → 
#        "We have a native Salesforce integration that syncs..."
#        [cites sources from KB]

# User: "What's the pricing for 200 users?"
# Agent: [searches KB] → [finds pricing doc] →
#        "For 200 users, our Enterprise plan starts at..."
```

---

## Measuring Knowledge Base Impact

Track how KB improves outreach:

```sql
-- See which messages used KB sources
SELECT 
    p.email,
    i.message_metadata->>'kb_sources_available' as kb_sources,
    i.created_at,
    i.response_received
FROM interactions i
JOIN prospects p ON i.prospect_id = p.id
WHERE i.type = 'email_sent'
ORDER BY i.created_at DESC;

-- Compare response rates: KB-backed vs generic
SELECT 
    CASE 
        WHEN (message_metadata->>'kb_sources_available')::int > 0 
        THEN 'KB-backed'
        ELSE 'Generic'
    END as message_type,
    COUNT(*) as total_sent,
    SUM(CASE WHEN response_received THEN 1 ELSE 0 END) as responses,
    ROUND(100.0 * SUM(CASE WHEN response_received THEN 1 ELSE 0 END) / COUNT(*), 2) as response_rate
FROM interactions
WHERE type = 'email_sent'
GROUP BY message_type;
```

---

## Troubleshooting

**"No KB sources found"**
- Check if documents are ingested: `SELECT COUNT(*) FROM rag_chunks;`
- Verify embeddings exist: `SELECT COUNT(*) FROM rag_chunks WHERE embedding IS NOT NULL;`
- Ensure query is specific enough

**"KB search slow"**
- Add index: `CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding ON rag_chunks USING ivfflat (embedding vector_l2_ops);`
- Reduce `top_k` parameter
- Check `EXPLAIN ANALYZE` on vector queries

**"Answers are generic"**
- Add more specific documentation
- Use metadata to filter results
- Increase `top_k` to get more context

---

## Next Steps

1. **Populate KB**: Ingest all product docs, case studies, pricing
2. **Test Retrieval**: Use `python -m app.query` to verify search quality
3. **Run Workflow**: See KB in action with `python examples/sdr_workflow.py`
4. **Monitor Impact**: Track response rates for KB-backed messages
5. **Iterate**: Add more content based on common prospect questions

---

## Summary

Your knowledge base is **not just a feature** - it's the **intelligence layer** that makes your SDR agent:

✅ **Accurate** - No hallucinations, only verified product info  
✅ **Personalized** - Cites relevant case studies and features  
✅ **Credible** - Sources are traceable and auditable  
✅ **Scalable** - Auto-research prospects and ingest company data  
✅ **Up-to-date** - Re-ingest docs to refresh agent knowledge  

**The knowledge base transforms generic outreach into intelligent, context-aware sales conversations.**

🌟 **Your RAG system is the star - the SDR agent is the delivery mechanism.** 🌟
