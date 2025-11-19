# SDR Agent System

Complete autonomous SDR (Sales Development Representative) agent for lead generation and personalized outreach.

## What It Does

The SDR agent can:
- 🔍 **Find leads** - Import from CSV, search LinkedIn, find company contacts
- 🧠 **Research prospects** - Enrich data from LinkedIn, company websites, tech stack detection
- 📊 **Qualify leads** - Score against your Ideal Customer Profile (ICP)
- ✍️ **Draft outreach** - Generate personalized emails and LinkedIn messages using LLM
- 📤 **Send messages** - Automate outreach via email and LinkedIn (with dry-run mode)
- 📈 **Track interactions** - Log all touches, manage follow-ups, conversation history

## Quick Start

### 1. Setup Database

```bash
# Start Postgres + pgvector
docker compose up -d

# Create prospect tables
export DATABASE_URL='postgresql+psycopg://rag:ragpw@localhost:5433/ragdb'
psql $DATABASE_URL -f sql/prospects.sql
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
pip install ollama sentence-transformers langdetect
```

### 3. Configure Environment

Create `.env` file:
```env
DATABASE_URL=postgresql+psycopg://rag:ragpw@localhost:5433/ragdb
LLM_MODEL=llama3.2

# Optional: for real email sending
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 4. Run Demo Workflow

```bash
# Run complete demo (import 3 example leads + full workflow)
python examples/sdr_workflow.py

# Interactive chat with agent
python examples/sdr_workflow.py --chat
```

## Usage Examples

### Import Leads from CSV

```bash
# Import from CSV file
python -m app.lead_finder import-csv leads.csv

# With custom column mapping
python -m app.lead_finder import-csv leads.csv --email-col "Email Address"
```

**CSV format:**
```csv
email,first_name,last_name,company_name,job_title,linkedin_url
john@example.com,John,Doe,Example Inc,VP of Sales,https://linkedin.com/in/johndoe
```

### Run SDR Workflow on Single Prospect

```bash
# Research → Qualify → Draft → Send (dry run)
python -m app.sdr_agent --workflow --prospect-id 1 --channel email --dry-run

# Real sending (requires SMTP config)
python -m app.sdr_agent --workflow --prospect-id 1 --channel email
```

### Interactive Chat with Agent

```bash
python -m app.sdr_agent --chat

# With prospect context
python -m app.sdr_agent --chat --prospect-id 1
```

Example prompts:
- "Research this prospect and tell me if they're a good fit"
- "Draft a personalized email focusing on their pain points"
- "What's the best approach to reach out to a VP of Sales?"

### Manage Prospects (CRM)

```python
from app.crm import ProspectManager, InteractionManager

# Create prospect
prospect_id = ProspectManager.create_prospect(
    email="jane@techcorp.com",
    first_name="Jane",
    last_name="Smith",
    company_name="TechCorp",
    job_title="Director of Marketing"
)

# Update stage
ProspectManager.update_stage(prospect_id, "qualified")

# Get prospects for follow-up
prospects = ProspectManager.get_prospects_for_followup(limit=20)

# Log interaction
InteractionManager.log_interaction(
    prospect_id=prospect_id,
    type="email_sent",
    content="Hello Jane...",
    subject="Quick question about TechCorp"
)
```

## Architecture

```
SDR Agent System
├── Prospect CRM (sql/prospects.sql)
│   ├── prospects - lead data + scoring
│   ├── interactions - activity log
│   ├── conversations - multi-turn dialogue
│   └── message_templates - outreach templates
│
├── Agent Core (app/sdr_agent.py)
│   ├── Research - enrich prospect data
│   ├── Qualify - score against ICP
│   ├── Draft - LLM-powered personalization
│   └── Outreach - send emails/LinkedIn
│
├── Tools (app/tools.py)
│   ├── Lead Enrichment - LinkedIn, company research, tech stack
│   ├── Outreach - email, LinkedIn messaging
│   └── Research - web search, fit analysis
│
└── Lead Finding (app/lead_finder.py)
    ├── CSV import
    ├── LinkedIn search (mock)
    └── Company contact finder (mock)
```

## Workflow Example

```python
from app.sdr_agent import SDRAgent

agent = SDRAgent(
    icp_criteria={
        "company_size": ["51-200", "201-500"],
        "industries": ["SaaS", "Technology"],
        "job_titles": ["VP", "Director", "Head of"],
        "technologies": ["Salesforce", "HubSpot"]
    }
)

# Full workflow: research → qualify → draft → send
result = agent.run_full_workflow(
    prospect_id=1,
    channel="email",
    dry_run=True  # Set False to actually send
)

# Outputs:
# {
#   "research": {...enriched data...},
#   "qualification": {"score": 0.75, "fit_level": "high"},
#   "draft": {"subject": "...", "body": "..."},
#   "outreach": {"status": "sent"}
# }
```

## Customization

### Define Your ICP

Edit `app/sdr_agent.py`:

```python
icp_criteria = {
    "company_size": ["11-50", "51-200"],  # Target company sizes
    "industries": ["FinTech", "SaaS"],    # Target industries
    "job_titles": ["CEO", "Founder"],     # Decision makers
    "technologies": ["Stripe", "Plaid"]   # Tech stack signals
}
```

### Add Message Templates

```sql
INSERT INTO message_templates (name, type, subject, body) VALUES (
    'cold_email_vp_sales',
    'email',
    'Quick question about {company_name}',
    'Hi {first_name},

I noticed {company_name} is using {technology}. We help companies like yours...

Are you open to a quick 15-min call next week?

Best,
Your Name'
);
```

### Integrate Real APIs

Replace mock implementations in `app/tools.py`:

- **LinkedIn**: Use LinkedIn Sales Navigator API or Phantombuster
- **Email Verification**: Use Hunter.io or ZeroBounce
- **Company Data**: Use Clearbit, Apollo.io, or BuiltWith
- **Tech Stack**: Use Wappalyzer or BuiltWith API

## Production Considerations

### Email Deliverability
- Use dedicated sending domain
- Warm up IP address gradually
- Implement SPF, DKIM, DMARC
- Monitor bounce rates and spam complaints
- Respect opt-outs and unsubscribes

### Rate Limiting
- LinkedIn: Max 100-200 connection requests/week
- Email: Start with 20-50/day, scale gradually
- Add random delays between messages

### Compliance
- GDPR: Track consent, allow data deletion
- CAN-SPAM: Include unsubscribe link, physical address
- CCPA: Honor do-not-sell requests

### Monitoring
- Track email open rates, click rates, reply rates
- Monitor lead scores over time
- A/B test message templates
- Alert on high bounce rates or spam complaints

## Integration with Existing RAG

The SDR agent can use your RAG knowledge base:

```python
from app import query as rag_query

# Research using knowledge base
docs = rag_query.search_similar_chunks(
    query_embedding=embed("Tell me about pricing"),
    top_k=3
)

# Use in outreach context
agent.draft_outreach(
    prospect_id=1,
    context=f"Relevant product info: {docs[0]['content']}"
)
```

## Troubleshooting

**"Ollama not found"**
```bash
# Install Ollama
brew install ollama  # macOS
# or download from ollama.ai

# Pull model
ollama pull llama3.2
```

**"SMTP authentication failed"**
- For Gmail: Use App Password, not regular password
- Enable "Less secure app access" or use OAuth

**"LinkedIn automation not working"**
- Mock implementation by default
- For production: Use LinkedIn API or automation tool
- Never violate LinkedIn's ToS

## Next Steps

1. **Import real leads**: Prepare CSV with your prospects
2. **Test outreach**: Run with `--dry-run` to review messages
3. **Refine ICP**: Adjust scoring criteria based on results
4. **Add templates**: Create message variants for A/B testing
5. **Monitor metrics**: Track open rates, replies, conversions
6. **Scale gradually**: Start small, increase volume over weeks

## Support

Questions? Check:
- Main README: `../README.md`
- Agent code: `app/sdr_agent.py`
- Examples: `examples/sdr_workflow.py`
- Database schema: `sql/prospects.sql`
