# CRM & Knowledge Base Integrations

Complete guide to setting up and using Typeform, HubSpot, and Salesforce integrations with the SDR Agent system.

## Table of Contents

- [Overview](#overview)
- [Requirements Satisfied](#requirements-satisfied)
- [Quick Start](#quick-start)
- [Typeform Integration](#typeform-integration)
- [HubSpot Integration](#hubspot-integration)
- [Salesforce Integration](#salesforce-integration)
- [Campaign Management](#campaign-management)
- [Admin UI](#admin-ui)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

---

## Overview

This system provides complete CRM and knowledge base integrations:

- **Typeform**: Ingest form responses into knowledge base
- **HubSpot**: Sync contacts, log activities, generate briefings
- **Salesforce**: Sync leads/contacts, log tasks, campaign triggers
- **Campaign System**: Automated prospect fetching and outreach queuing
- **Admin UI**: Web interface for managing all integrations

---

## Requirements Satisfied

### ✅ FR-KB-001: Knowledge Base Ingestion
- **Typeform Integration**: Connect Typeform account via OAuth, fetch form responses, auto-ingest as Q&A pairs
- **Document Uploads**: Admin UI for uploading .pdf, .docx, .txt, etc.

### ✅ FR-KB-002: Parse and Index
- All documents parsed via `app/convert.py`
- Indexed into pgvector with 384-d embeddings
- Full-text and semantic search available

### ✅ FR-CRM-001: HubSpot OAuth 2.0
- Complete OAuth flow implemented
- Secure token storage and refresh
- Contact/company data fetching

### ✅ FR-CRM-002: Salesforce OAuth 2.0
- Complete OAuth flow implemented  
- Secure token storage and refresh
- Lead/contact/account data fetching

### ✅ FR-CRM-003: Campaign-Triggered Data Fetch
- Campaign system with multiple trigger types (manual, scheduled, event)
- Automatic contact import based on CRM filters
- Queue management for prospect processing

### ✅ FR-CRM-004: Temporary Data Storage
- Local CRM database (`prospects`, `interactions`, `conversations`)
- `crm_sync_metadata` table tracks external IDs
- Full prospect lifecycle management

### ✅ FR-CRM-005: Natural Language Briefing
- `generate_prospect_briefing()` creates pre-call summaries
- Integrates knowledge base context
- Includes interaction history and CRM data

### ✅ FR-CRM-006: Update CRM with Call Logs
- HubSpot: `sync_call_log()` creates notes and call activities
- Salesforce: `sync_call_log()` creates tasks with details
- Bidirectional sync maintains data integrity

---

## Quick Start

### 1. Setup Database Schema

```bash
# Run integration schema (after prospects.sql)
psql $DATABASE_URL -f sql/integrations.sql
```

### 2. Configure Environment Variables

Create `.env`:

```bash
# Database
DATABASE_URL=postgresql+psycopg://rag:ragpw@localhost:5433/ragdb

# Typeform
TYPEFORM_CLIENT_ID=your_client_id
TYPEFORM_CLIENT_SECRET=your_client_secret
TYPEFORM_REDIRECT_URI=http://localhost:8000/oauth/typeform/callback

# HubSpot
HUBSPOT_CLIENT_ID=your_client_id
HUBSPOT_CLIENT_SECRET=your_client_secret
HUBSPOT_REDIRECT_URI=http://localhost:8000/oauth/hubspot/callback

# Salesforce
SALESFORCE_CLIENT_ID=your_client_id
SALESFORCE_CLIENT_SECRET=your_client_secret
SALESFORCE_REDIRECT_URI=http://localhost:8000/oauth/salesforce/callback
SALESFORCE_INSTANCE_URL=https://login.salesforce.com  # or test.salesforce.com

# Admin UI
FLASK_SECRET_KEY=your_random_secret_key
ADMIN_UI_PORT=8000
UPLOAD_FOLDER=/tmp/sdr_uploads
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start Admin UI

```bash
python app/admin_ui.py
```

Navigate to http://localhost:8000

---

## Typeform Integration

### Setup

1. **Create Typeform App**:
   - Go to https://admin.typeform.com/account#/applications
   - Create new application
   - Add redirect URI: `http://localhost:8000/oauth/typeform/callback`
   - Copy Client ID and Secret to `.env`

2. **Connect via Admin UI**:
   - Open http://localhost:8000
   - Click "Connect" next to Typeform
   - Authorize the application
   - You'll be redirected back with token stored

### Usage

#### Via Admin UI

```python
# 1. List forms
Navigate to: /typeform/forms

# 2. Ingest form responses
Click "Ingest to KB" next to any form
```

#### Via Code

```python
from app.typeform_integration import ingest_typeform, list_typeform_forms

# List all forms
forms = list_typeform_forms()
print(forms)

# Ingest form responses
result = ingest_typeform(form_id="abc123")
# {
#     "form_id": "abc123",
#     "responses_count": 50,
#     "chunks_count": 150,
#     "chunks_ingested": 150
# }
```

### How It Works

1. **OAuth**: Securely authenticates with Typeform
2. **Fetch Responses**: Retrieves all form submissions
3. **Parse Q&A**: Converts each response into question-answer pairs
4. **Convert**: Creates Markdown document with all Q&A
5. **Chunk**: Breaks into RAG-optimized chunks
6. **Ingest**: Stores in pgvector for semantic search

---

## HubSpot Integration

### Setup

1. **Create HubSpot App**:
   - Go to https://app.hubspot.com/developers
   - Create app
   - Add scopes: `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.objects.companies.read`, `timeline`
   - Add redirect URI: `http://localhost:8000/oauth/hubspot/callback`
   - Copy Client ID and Secret to `.env`

2. **Connect via Admin UI**:
   - Open http://localhost:8000
   - Click "Connect" next to HubSpot
   - Authorize the application

### Usage

#### Import Contacts

```python
from app.hubspot_integration import import_hubspot_contact, HubSpotSync

# Import single contact
prospect_id = import_hubspot_contact(contact_id="12345")

# Import by filter
filters = [{"propertyName": "lifecyclestage", "operator": "EQ", "value": "lead"}]
prospect_ids = HubSpotSync.import_contacts_by_filter(filters, limit=100)
```

#### Generate Briefing

```python
from app.hubspot_integration import generate_prospect_briefing

briefing = generate_prospect_briefing(prospect_id=1)
print(briefing)
# **Contact:** John Doe
# **Title:** VP of Sales
# **Company:** Acme Corp
# ...
```

#### Sync Call Logs

```python
from app.hubspot_integration import sync_interaction_to_hubspot

# After logging interaction locally
sync_interaction_to_hubspot(prospect_id=1, interaction_id=42)
# Creates note + call activity in HubSpot
```

### Campaign Integration

```python
from app.campaign_manager import create_campaign, trigger_campaign

# Create HubSpot campaign
campaign_id = create_campaign(
    name="Q1 Leads Outreach",
    crm_source="hubspot",
    crm_filters={"list_id": "123"},  # HubSpot list ID
    max_prospects=100
)

# Trigger campaign (imports contacts)
result = trigger_campaign(campaign_id)
# {
#     "prospects_imported": 87,
#     "prospect_ids": [1, 2, 3, ...]
# }
```

---

## Salesforce Integration

### Setup

1. **Create Connected App**:
   - Setup → App Manager → New Connected App
   - Enable OAuth Settings
   - Add scopes: `api`, `refresh_token`, `offline_access`
   - Callback URL: `http://localhost:8000/oauth/salesforce/callback`
   - Copy Consumer Key and Secret to `.env` as `SALESFORCE_CLIENT_ID` and `SALESFORCE_CLIENT_SECRET`

2. **Connect via Admin UI**:
   - Open http://localhost:8000
   - Click "Connect" next to Salesforce
   - Authorize the application

### Usage

#### Import Leads/Contacts

```python
from app.salesforce_integration import import_salesforce_lead, import_salesforce_contact

# Import lead
prospect_id = import_salesforce_lead(lead_id="00Q...")

# Import contact
prospect_id = import_salesforce_contact(contact_id="003...")
```

#### Campaign Integration

```python
from app.salesforce_integration import import_campaign_members

# Import all members from Salesforce campaign
prospect_ids = import_campaign_members(campaign_id="701...", limit=100)
```

#### Sync Call Logs

```python
from app.salesforce_integration import sync_interaction_to_salesforce

# Sync interaction to Salesforce as Task
sync_interaction_to_salesforce(prospect_id=1, interaction_id=42)
# Creates completed task with call details
```

---

## Campaign Management

### Campaign Types

1. **Manual**: Admin triggers via UI or API
2. **Scheduled**: Auto-triggers at intervals
3. **Event**: Triggered by webhooks
4. **Webhook**: External system triggers

### Create Campaign

```python
from app.campaign_manager import create_campaign

campaign_id = create_campaign(
    name="Weekly New Leads",
    description="Outreach to new leads from HubSpot",
    trigger_type="scheduled",
    trigger_config={"interval": "7 days"},
    crm_source="hubspot",
    crm_filters={"lifecyclestage": "lead"},
    max_prospects=50,
    agent_config={"personalization_level": "high"}
)
```

### Schedule Campaign

```python
from app.campaign_manager import CampaignScheduler

# Setup daily trigger
CampaignScheduler.setup_campaign_schedule(
    campaign_id=1,
    interval="1 day",  # PostgreSQL interval syntax
    start_time=datetime.now()
)

# Run scheduler (call periodically via cron)
CampaignScheduler.check_scheduled_campaigns()
```

### Process Campaign Queue

```python
from app.campaign_manager import process_campaign_queue
from app.sdr_agent import SDRAgent

# Define agent callback
def agent_callback(prospect):
    agent = SDRAgent()
    agent.draft_outreach(
        prospect_id=prospect["prospect_id"],
        context={"campaign": "Q1 Leads"}
    )

# Process all prospects in queue
processed = process_campaign_queue(campaign_id=1, agent_callback=agent_callback)
print(f"Processed {processed} prospects")
```

---

## Admin UI

### Features

- **Dashboard**: Integration status, quick actions
- **Document Upload**: Drag-and-drop with auto-ingestion
- **OAuth Connections**: One-click setup for Typeform, HubSpot, Salesforce
- **Campaign Management**: Create, trigger, monitor campaigns
- **Typeform Forms**: List and ingest form responses

### Screens

#### Dashboard (`/`)
- Integration connection status
- Document upload zone
- Campaign shortcuts

#### Campaigns (`/campaigns`)
- List all campaigns
- Trigger campaigns manually
- View campaign stats

#### Create Campaign (`/campaigns/create`)
- Form to define campaign parameters
- CRM source selection
- Trigger configuration

#### Typeform Forms (`/typeform/forms`)
- List all forms from connected account
- One-click ingestion

### API Endpoints

#### Upload Document
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@document.pdf" \
  -F "auto_ingest=true"
```

#### Create Campaign
```bash
curl -X POST http://localhost:8000/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Campaign",
    "crm_source": "hubspot",
    "trigger_type": "manual"
  }'
```

#### List Campaigns
```bash
curl http://localhost:8000/api/campaigns
```

---

## API Reference

### Typeform

```python
# Authentication
from app.typeform_integration import authenticate_typeform, complete_typeform_oauth

auth_url = authenticate_typeform()
token_data = complete_typeform_oauth(code="...")

# Ingestion
from app.typeform_integration import ingest_typeform, list_typeform_forms

forms = list_typeform_forms()
result = ingest_typeform(form_id="abc123")
```

### HubSpot

```python
# Authentication
from app.hubspot_integration import authenticate_hubspot, complete_hubspot_oauth

auth_url = authenticate_hubspot()
token_data = complete_hubspot_oauth(code="...")

# Sync
from app.hubspot_integration import import_hubspot_contact, sync_interaction_to_hubspot, generate_prospect_briefing

prospect_id = import_hubspot_contact(contact_id="123")
briefing = generate_prospect_briefing(prospect_id=1)
sync_interaction_to_hubspot(prospect_id=1, interaction_id=42)
```

### Salesforce

```python
# Authentication
from app.salesforce_integration import authenticate_salesforce, complete_salesforce_oauth

auth_url = authenticate_salesforce()
token_data = complete_salesforce_oauth(code="...")

# Sync
from app.salesforce_integration import import_salesforce_lead, import_campaign_members, sync_interaction_to_salesforce

prospect_id = import_salesforce_lead(lead_id="00Q...")
prospect_ids = import_campaign_members(campaign_id="701...")
sync_interaction_to_salesforce(prospect_id=1, interaction_id=42)
```

### Campaigns

```python
from app.campaign_manager import create_campaign, trigger_campaign, get_campaign_stats

# Create
campaign_id = create_campaign(name="My Campaign", crm_source="hubspot")

# Trigger
result = trigger_campaign(campaign_id=1)

# Stats
stats = get_campaign_stats(campaign_id=1)
# {"total": 100, "pending": 25, "processed": 70, "failed": 5}
```

---

## Troubleshooting

### OAuth Errors

**Problem**: "OAuth failed: No code received"
- **Solution**: Check redirect URI matches exactly in provider settings
- **Solution**: Ensure app has correct scopes enabled

**Problem**: Token refresh fails
- **Solution**: Re-authenticate via Admin UI
- **Solution**: Check `oauth_tokens` table for expired tokens

### Import Errors

**Problem**: "No valid access token found"
- **Solution**: Complete OAuth flow first
- **Solution**: Check token in database: `SELECT * FROM oauth_tokens WHERE provider = 'hubspot'`

**Problem**: Rate limit exceeded
- **Solution**: Add delays between imports
- **Solution**: Reduce `max_prospects` in campaign config

### Ingestion Errors

**Problem**: Chunks not appearing in knowledge base
- **Solution**: Verify `DATABASE_URL` is correct
- **Solution**: Check `rag_chunks` table: `SELECT COUNT(*) FROM rag_chunks`

**Problem**: Typeform form has no responses
- **Solution**: Verify form has submissions in Typeform dashboard
- **Solution**: Check date filters if using `since` parameter

---

## Production Checklist

Before deploying to production:

- [ ] Use HTTPS for all OAuth redirect URIs
- [ ] Rotate `FLASK_SECRET_KEY` regularly
- [ ] Enable rate limiting on API endpoints
- [ ] Set up monitoring for failed webhook events
- [ ] Configure backup for `oauth_tokens` table
- [ ] Implement token encryption at rest
- [ ] Add audit logging for all CRM syncs
- [ ] Set up alerts for failed campaign triggers
- [ ] Use environment-specific OAuth apps (dev, staging, prod)
- [ ] Enable CORS restrictions for API endpoints

---

## Next Steps

1. **Add More CRM Filters**: Extend campaign filters for advanced targeting
2. **Webhook Handlers**: Implement real-time event processing
3. **Bulk Operations**: Add batch import/export for large datasets
4. **Advanced Briefings**: Use LLM to generate richer prospect insights
5. **Analytics Dashboard**: Track campaign performance metrics
6. **Multi-user Support**: Add authentication and user permissions

---

## Support

For questions or issues:
- Check logs in `app/admin_ui.py` (Flask debug mode)
- Review database schema in `sql/integrations.sql`
- Test OAuth flows in browser dev tools (Network tab)
- Verify environment variables with `python -c "import os; print(os.getenv('HUBSPOT_CLIENT_ID'))"`
