# Gemini File API Integration Guide

## Overview

Your SDR system now supports **Google's Gemini File API** as an optional turbo mode alongside your local RAG system. This gives you the best of both worlds:

**Local RAG (Default)**
- ✅ 100% local and private
- ✅ Free (no API costs)
- ✅ Works offline
- ✅ Full control over data

**Gemini RAG (Optional)**
- ✅ Automatic optimal chunking
- ✅ Multimodal support (images, PDFs, code)
- ✅ Built-in citations
- ✅ Sub-2-second parallel search
- ✅ State-of-the-art embeddings
- ✅ Cost-effective ($0.15/1M tokens for indexing, free queries)

**Hybrid Mode (Best of Both)**
- ✅ Combines local + Gemini results
- ✅ Cross-validates answers
- ✅ Maximum coverage

---

## Setup

### 1. Install Dependencies

```bash
pip install google-generativeai
```

(Already added to `requirements.txt`)

### 2. Get Google API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Create an API key
3. Add to `.env`:

```bash
echo "GOOGLE_API_KEY=your_api_key_here" >> .env
```

### 3. Verify Installation

```bash
python -m app.gemini_rag --list
```

---

## Quick Start

### Create a Corpus

```bash
# Create corpus for product docs
python -m app.gemini_rag --create-corpus product_docs
```

### Upload Documents

```bash
# Upload single file
python -m app.gemini_rag --corpus product_docs --upload docs/features.pdf

# Upload entire directory
python -m app.gemini_rag --corpus product_docs --upload-dir docs/
```

**Supported formats:** PDF, DOCX, TXT, JSON, Markdown, Python, JavaScript, TypeScript, Java, C++, images (PNG, JPG), and [more](https://ai.google.dev/gemini-api/docs/file-search)

### Query with Citations

```bash
# Query Gemini corpus
python -m app.gemini_rag --corpus product_docs --query "What are the key features?"

# Hybrid query (local + Gemini)
python -m app.gemini_rag --corpus product_docs --query "pricing information" --hybrid
```

---

## Python API

### Basic Usage

```python
from app.gemini_rag import GeminiRAG

# Initialize
rag = GeminiRAG()

# Create corpus
rag.create_corpus("product_docs", "Product Documentation")

# Upload files
rag.upload_file("product_docs", "docs/features.pdf")
rag.upload_directory("product_docs", "docs/", recursive=True)

# Query with automatic citations
result = rag.query("What are the main features?", corpus_name="product_docs")

print(result['answer'])
for citation in result['citations']:
    print(f"  📖 Source: {citation['source']}")
    print(f"     {citation['content_preview'][:100]}...")
```

### Hybrid Mode (Local + Gemini)

```python
# Combine both RAG systems
result = rag.hybrid_query(
    question="How does our pricing work?",
    use_local=True,
    use_gemini=True,
    corpus_name="product_docs"
)

print("🌟 COMBINED ANSWER:")
print(result['combined_answer'])

print("\n📚 LOCAL RAG:")
print(result['local']['answer'])

print("\n🤖 GEMINI RAG:")
print(result['gemini']['answer'])
```

---

## SDR Agent Integration

### The agent automatically uses Gemini if available:

```python
from app.tools import KnowledgeBaseTools

# Local search (default)
results = KnowledgeBaseTools.search_knowledge(
    "product benefits for SaaS companies"
)

# Gemini search
results = KnowledgeBaseTools.search_knowledge(
    "product benefits for SaaS companies",
    use_gemini=True,
    corpus_name="product_docs"
)

# Answer with RAG
answer = KnowledgeBaseTools.answer_from_knowledge(
    "Does our product integrate with Salesforce?",
    use_gemini=True,
    corpus_name="product_docs"
)

# Hybrid mode (best results)
answer = KnowledgeBaseTools.answer_from_knowledge(
    "What ROI can customers expect?",
    hybrid=True,
    corpus_name="product_docs"
)
```

### Configure Agent to Use Gemini

```python
from app.sdr_agent import SDRAgent

agent = SDRAgent()

# Draft email - will use Gemini if GOOGLE_API_KEY is set
draft = agent.draft_outreach(
    prospect_id=1,
    channel="email"
)

# The draft will include:
# - Local KB search results
# - Gemini corpus search (if configured)
# - Combined, high-quality personalization
```

---

## Use Cases

### 1. Multimodal Product Documentation

Upload PDFs, diagrams, screenshots, code samples:

```python
rag = GeminiRAG()
rag.create_corpus("visual_docs", "Product Documentation with Images")

# Upload architecture diagrams (PNG/JPG)
rag.upload_file("visual_docs", "diagrams/architecture.png")

# Upload code samples
rag.upload_file("visual_docs", "examples/integration.py")

# Upload presentation decks (PPTX)
rag.upload_file("visual_docs", "decks/product_overview.pptx")

# Query understands images and code!
result = rag.query(
    "Explain the architecture diagram and show code examples",
    corpus_name="visual_docs"
)
```

### 2. Fast Prospect Research

Research companies and get instant answers:

```python
from app.tools import LeadEnrichment

# Research company (auto-ingests to local KB)
LeadEnrichment.research_company("stripe.com", ingest_to_kb=True)

# Also upload to Gemini for multimodal understanding
rag.upload_file("prospect_research", "tmp/stripe_com.md")

# Get comprehensive analysis
result = rag.hybrid_query(
    "What does Stripe do and how could our product help them?",
    corpus_name="prospect_research"
)
```

### 3. Industry-Specific Corpora

Organize by industry for targeted personalization:

```python
# Create industry-specific corpora
rag.create_corpus("fintech_kb", "FinTech Industry Knowledge")
rag.create_corpus("saas_kb", "SaaS Industry Knowledge")
rag.create_corpus("healthcare_kb", "Healthcare Industry Knowledge")

# Upload relevant case studies
rag.upload_directory("fintech_kb", "case_studies/fintech/")
rag.upload_directory("saas_kb", "case_studies/saas/")

# Query the right corpus for each prospect
if prospect['industry'] == 'FinTech':
    result = rag.query(
        f"case studies for {prospect['job_title']} in FinTech",
        corpus_name="fintech_kb"
    )
```

### 4. Parallel Multi-Corpus Search

Search across all corpora simultaneously:

```python
# Search multiple corpora in parallel
result = rag.query(
    "customer success stories with quantified ROI",
    corpora=["fintech_kb", "saas_kb", "healthcare_kb"]
)

# Sub-2-second response across 3 corpora!
```

---

## Cost Optimization

### Pricing Breakdown

- **Indexing**: $0.15 per 1M tokens (one-time)
- **Storage**: Free
- **Query embeddings**: Free
- **LLM generation**: Standard Gemini API rates

### Optimization Tips

1. **Upload once, query many times** - Indexing is one-time cost
2. **Use local for high-volume** - Local is free for unlimited queries
3. **Hybrid for critical paths** - Combine local + Gemini for important prospect research
4. **Organize by corpus** - Separate corpora reduce search scope

### Cost Example

```python
# Typical setup:
# - 100 product docs (500 pages) = ~500K tokens = $0.075 to index
# - Unlimited free queries
# - LLM generation: ~$0.001 per query

# Total: ~$0.10 to set up, then <$0.01 per prospect researched
```

---

## Migration from Local to Gemini

### Option 1: Side-by-Side (Recommended)

Keep both systems running:

```python
# Local for high-volume, routine queries
local_result = KnowledgeBaseTools.search_knowledge("pricing")

# Gemini for complex, multimodal queries
gemini_result = KnowledgeBaseTools.search_knowledge(
    "explain this architecture diagram",
    use_gemini=True
)
```

### Option 2: Gradual Migration

Start with hybrid mode, then shift to Gemini:

```python
# Week 1: Hybrid (validate quality)
answer = KnowledgeBaseTools.answer_from_knowledge(
    question,
    hybrid=True
)

# Week 2+: Pure Gemini if quality is good
answer = KnowledgeBaseTools.answer_from_knowledge(
    question,
    use_gemini=True
)
```

### Option 3: Upload Existing Corpus

Upload your existing local documents to Gemini:

```python
rag = GeminiRAG()
rag.create_corpus("migrated_kb", "Migrated Knowledge Base")

# Upload all documents from local ingest
import os
from pathlib import Path

docs_dir = Path("data/")  # Your ingested docs
for file_path in docs_dir.rglob("*.md"):
    rag.upload_file("migrated_kb", str(file_path))
```

---

## Advanced Features

### 1. Custom Metadata

```python
# Upload with rich metadata
rag.upload_file(
    "product_docs",
    "case_studies/acme_corp.pdf",
    metadata={
        "industry": "SaaS",
        "company_size": "201-500",
        "publish_date": "2024-11-01",
        "roi_percentage": 40
    }
)

# Query can filter by metadata (future feature)
```

### 2. Multi-Turn Conversations

```python
# Gemini maintains conversation context
conversation_history = []

q1 = "What are our key features?"
r1 = rag.query(q1, corpus_name="product_docs")
conversation_history.append((q1, r1['answer']))

# Follow-up understands context
q2 = "How much do those cost?"  # "those" = features from q1
r2 = rag.query(q2, corpus_name="product_docs")
```

### 3. Automatic Citation Verification

```python
result = rag.query("What's our refund policy?", corpus_name="legal_docs")

# Gemini provides verifiable citations
for citation in result['citations']:
    print(f"Claim sourced from: {citation['source']}")
    print(f"URI: {citation['uri']}")
    print(f"Preview: {citation['content_preview']}")
    
# Use for compliance, fact-checking, auditing
```

---

## Comparison: Local vs Gemini

| Feature | Local RAG | Gemini RAG | Hybrid |
|---------|-----------|------------|--------|
| **Privacy** | ✅ 100% private | ⚠️ Cloud-hosted | 🔀 Mixed |
| **Cost** | ✅ Free | 💰 ~$0.15/1M tokens indexing | 💰 Small cost |
| **Speed** | ⚡ ~200ms | ⚡⚡ <2s parallel | ⚡ ~2s |
| **Multimodal** | ❌ Text only | ✅ Images, PDFs, code | ✅ Via Gemini |
| **Citations** | ⚠️ Manual | ✅ Automatic | ✅ Both |
| **Offline** | ✅ Works offline | ❌ Requires internet | 🔀 Degrades gracefully |
| **Setup** | 🔧 Self-managed | ✅ Fully managed | 🔧 Both |
| **Chunking** | 🔧 Manual config | ✅ Automatic optimal | ✅ Both |

---

## Troubleshooting

### "ImportError: No module named 'google.generativeai'"

```bash
pip install google-generativeai
```

### "API key not found"

```bash
export GOOGLE_API_KEY='your_key_here'
# Or add to .env file
```

### "File upload failed"

- Check file format is supported
- Verify file size (<20MB for free tier)
- Try waiting and retrying (rate limits)

### "No corpora available"

```bash
# List corpora
python -m app.gemini_rag --list

# Create one
python -m app.gemini_rag --create-corpus my_corpus
```

---

## Best Practices

1. **Start with local** - Build and test with free local RAG
2. **Add Gemini for scale** - Use Gemini when you need speed/multimodal
3. **Hybrid for critical** - Use hybrid mode for important prospect research
4. **Organize by use case** - Create separate corpora (product, case_studies, industry)
5. **Monitor costs** - Track indexing costs, optimize corpus structure
6. **Validate citations** - Always check citations for accuracy
7. **Keep local synced** - Upload to Gemini, but keep local backup

---

## Production Checklist

- [ ] Google API key configured in production
- [ ] Corpora created for each major content type
- [ ] Documents uploaded and indexed
- [ ] Citation format meets compliance requirements
- [ ] Cost monitoring set up
- [ ] Fallback to local if Gemini unavailable
- [ ] Test queries validated for quality
- [ ] SDR agent configured with appropriate mode

---

## Next Steps

1. **Set up Gemini**: Get API key and create first corpus
2. **Upload docs**: Start with product documentation
3. **Test queries**: Validate answer quality vs local
4. **Enable in SDR**: Configure agent to use hybrid mode
5. **Monitor results**: Track response rates with Gemini-powered outreach

🌟 **Gemini File API transforms your knowledge base from text-only to multimodal intelligence!** 🌟
