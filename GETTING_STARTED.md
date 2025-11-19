# Getting Started with SDR Agent System

Complete step-by-step guide to get the SDR Agent System running with all integrations.

---

## Table of Contents

1. [Quick Start (5 minutes)](#quick-start-5-minutes)
2. [Full Setup with Integrations (30 minutes)](#full-setup-with-integrations)
3. [Testing the System](#testing-the-system)
4. [Common Issues](#common-issues)
5. [What's Next](#whats-next)

---

## Quick Start (5 minutes)

Get the basic RAG system running without any integrations.

### Step 1: Prerequisites

```bash
# Required:
- Python 3.11+
- Docker & Docker Compose
- Git

# Check versions:
python3 --version  # Should be 3.11 or higher
docker --version
docker compose version
```

### Step 2: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/ilkecodes/sdr-agent-system
cd sdr-agent-system/rag-min

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Start Database

```bash
# Start PostgreSQL with pgvector
docker compose up -d

# Wait 10 seconds for database to initialize
sleep 10

# Initialize database schema
export DATABASE_URL='postgresql+psycopg://rag:ragpw@localhost:5433/ragdb'
psql $DATABASE_URL -f sql/init.sql
psql $DATABASE_URL -f sql/prospects.sql
psql $DATABASE_URL -f sql/integrations.sql
```

### Step 4: Test Basic RAG

```bash
# Ingest a sample document
python app/ingest.py data/sample.txt

# Query the knowledge base
python app/query.py "What is this document about?"
```

**✅ Success!** If you see results, the basic system is working.

---

## Full Setup with Integrations

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Your Setup Options                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Basic RAG Only           ← Start here (5 min)               │
│  2. + CRM Integrations       ← Add HubSpot/Salesforce (20 min)  │
│  3. + Calendar Integrations  ← Add Google/Outlook (15 min)      │
│  4. + SDR Agent              ← Full automation (10 min)         │
└─────────────────────────────────────────────────────────────────┘
```

### Option 1: Basic RAG Only ✅ (Already Done Above)

You've completed this! Move to Option 2 or 3 to add integrations.

---

### Option 2: Add CRM Integrations (Typeform, HubSpot, Salesforce)

These integrations enable:
- **Typeform**: Auto-import form responses to knowledge base
- **HubSpot**: Sync contacts, log calls, generate briefings
- **Salesforce**: Import leads, sync data, log activities
- **Campaigns**: Automated prospect importing with triggers

#### Prerequisites

You'll need developer accounts:
- [Typeform](https://admin.typeform.com/signup)
- [HubSpot Developer Account](https://developers.hubspot.com/)
- [Salesforce Developer Account](https://developer.salesforce.com/)

#### Setup Typeform (Optional)

1. **Create Typeform App**
   - Go to https://admin.typeform.com/account#/section/tokens
   - Click "Generate a new token" or create OAuth app
   - Note your Client ID and Client Secret

2. **Configure Environment**
   ```bash
   export TYPEFORM_CLIENT_ID="your_client_id"
   export TYPEFORM_CLIENT_SECRET="your_client_secret"
   ```

#### Setup HubSpot (Optional)

1. **Create HubSpot App**
   - Go to https://app.hubspot.com/
   - Navigate to Settings → Integrations → Private Apps
   - Create new private app
   - Add scopes: `crm.objects.contacts.read`, `crm.objects.contacts.write`
   - Note your Client ID and Secret

2. **Configure Environment**
   ```bash
   export HUBSPOT_CLIENT_ID="your_client_id"
   export HUBSPOT_CLIENT_SECRET="your_client_secret"
   ```

#### Setup Salesforce (Optional)

1. **Create Connected App**
   - Log in to Salesforce
   - Setup → Apps → App Manager → New Connected App
   - Enable OAuth Settings
   - Callback URL: `http://localhost:8000/oauth/salesforce/callback`
   - Scopes: `api`, `refresh_token`, `offline_access`
   - Note Consumer Key (Client ID) and Consumer Secret

2. **Configure Environment**
   ```bash
   export SALESFORCE_CLIENT_ID="your_consumer_key"
   export SALESFORCE_CLIENT_SECRET="your_consumer_secret"
   ```

#### Test CRM Integrations

```bash
# Set Flask secret
export FLASK_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')

# Start Admin UI
python app/admin_ui.py

# Visit http://localhost:8000
# Click "Connect" for each CRM you configured
# Complete OAuth flow in browser
```

**📖 See [`docs/CRM_INTEGRATIONS.md`](docs/CRM_INTEGRATIONS.md) for complete CRM setup guide**

---

### Option 3: Add Calendar Integrations (Google Calendar, Outlook)

These integrations enable:
- **Real-time availability checking** (FR-CAL-002)
- **Automated meeting booking** (FR-CAL-003)
- **Google Meet or Microsoft Teams links**
- **Email invitations to prospects**

#### Prerequisites

You'll need:
- Google Cloud Account (for Google Calendar)
- Microsoft Azure Account (for Outlook Calendar)

Choose ONE calendar provider to start (you can add both later).

#### Setup Google Calendar

1. **Create Google Cloud Project**
   - Go to https://console.cloud.google.com/
   - Create new project: "SDR Agent Calendar"
   - Enable Google Calendar API:
     - APIs & Services → Library
     - Search "Google Calendar API"
     - Click Enable

2. **Create OAuth Credentials**
   - APIs & Services → Credentials
   - Create Credentials → OAuth client ID
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/oauth/google/callback`
   - Copy Client ID and Client Secret

3. **Configure OAuth Consent Screen**
   - User Type: External
   - Add scope: `https://www.googleapis.com/auth/calendar`
   - Add test users (your email)

4. **Configure Environment**
   ```bash
   export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
   export GOOGLE_CLIENT_SECRET="your-client-secret"
   export GOOGLE_REDIRECT_URI="http://localhost:8000/oauth/google/callback"
   ```

#### Setup Microsoft Outlook Calendar

1. **Register Azure AD App**
   - Go to https://portal.azure.com/
   - Azure Active Directory → App registrations
   - New registration:
     - Name: "SDR Agent Calendar"
     - Supported accounts: Accounts in any organizational directory and personal Microsoft accounts
     - Redirect URI: Web - `http://localhost:8000/oauth/outlook/callback`

2. **Configure API Permissions**
   - API permissions → Add permission
   - Microsoft Graph → Delegated permissions
   - Add: `Calendars.ReadWrite`, `offline_access`
   - Grant admin consent

3. **Create Client Secret**
   - Certificates & secrets → New client secret
   - Copy the VALUE immediately (can't view again!)

4. **Configure Environment**
   ```bash
   export OUTLOOK_CLIENT_ID="your-application-id"
   export OUTLOOK_CLIENT_SECRET="your-client-secret-value"
   export OUTLOOK_TENANT_ID="common"
   export OUTLOOK_REDIRECT_URI="http://localhost:8000/oauth/outlook/callback"
   ```

#### Test Calendar Integration

```bash
# Make sure Admin UI is running
python app/admin_ui.py

# Visit http://localhost:8000
# You'll see "Google Calendar" and "Outlook Calendar" in integrations
# Click "Connect" for your chosen provider
# Complete OAuth flow
# Click "Manage Calendar" to see:
#   - Your next available time slots
#   - Quick meeting booking form
#   - Upcoming meetings
```

**📖 See [`docs/CALENDAR_INTEGRATIONS.md`](docs/CALENDAR_INTEGRATIONS.md) for complete calendar setup guide**

---

### Option 4: Run Full SDR Agent

Once you have integrations set up, run the full SDR agent workflow.

```bash
# Run SDR demo workflow
python examples/sdr_workflow.py

# Interactive chat with agent
python examples/sdr_workflow.py --chat
```

---

## Testing the System

### Test 1: Knowledge Base Query

```bash
python app/query.py "What are the main features?"
```

**Expected**: You should see relevant chunks from your ingested documents.

### Test 2: Document Upload via Admin UI

1. Start Admin UI: `python app/admin_ui.py`
2. Visit http://localhost:8000
3. Upload a PDF/DOCX file
4. Check "Auto-ingest to knowledge base"
5. Click Upload

**Expected**: File processes successfully, chunks ingested.

### Test 3: Calendar Availability Check

```python
# Create test script: test_calendar.py
from app.calendar_manager import CalendarManager
from datetime import datetime, timedelta

user_id = "default_user"
manager = CalendarManager(user_id)

if manager.is_authenticated():
    start = datetime.utcnow()
    end = start + timedelta(days=7)
    slots = manager.check_availability(start, end, duration_minutes=30)
    print(f"Found {len(slots)} available 30-min slots")
    for slot in slots[:5]:
        print(f"  - {slot.start}")
else:
    print("Not authenticated - connect calendar via Admin UI first")
```

```bash
python test_calendar.py
```

### Test 4: Quick Meeting Booking

```python
# Create test script: test_booking.py
from app.calendar_manager import quick_book_meeting

result = quick_book_meeting(
    user_id="default_user",
    customer_email="test@example.com",
    title="Test Meeting",
    duration_minutes=30,
    description="Testing automated booking"
)

if result:
    print(f"✅ Booked for {result['start_time']}")
else:
    print("❌ No slots available")
```

```bash
python test_booking.py
```

### Test 5: CRM Integration Examples

```bash
# Run CRM integration examples
python examples/integration_workflow.py
```

### Test 6: Calendar Integration Examples

```bash
# Run calendar integration examples
python examples/calendar_workflow.py
```

---

## Common Issues

### Issue: "ModuleNotFoundError"

**Solution**: Install dependencies
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Issue: "Connection refused" to database

**Solution**: Start Docker
```bash
docker compose up -d
docker compose ps  # Check if running
```

### Issue: "Table does not exist"

**Solution**: Run SQL schema files
```bash
export DATABASE_URL='postgresql+psycopg://rag:ragpw@localhost:5433/ragdb'
psql $DATABASE_URL -f sql/init.sql
psql $DATABASE_URL -f sql/prospects.sql
psql $DATABASE_URL -f sql/integrations.sql
```

### Issue: "OAuth token invalid"

**Solution**: Reconnect via Admin UI
1. Visit http://localhost:8000
2. Click "Connect" for the integration
3. Complete OAuth flow again

### Issue: "No available slots found"

**Cause**: Your calendar is fully booked or not connected

**Solution**:
1. Check calendar connection in Admin UI
2. Try longer time range: `days_ahead=14`
3. Check actual calendar has free time

### Issue: Calendar OAuth redirect fails

**Solution**: Check redirect URI matches exactly
- Google: Must match exactly in Google Cloud Console
- Outlook: Must match exactly in Azure Portal
- Use `http://localhost:8000/oauth/google/callback` (no trailing slash)

---

## Environment Variables Reference

Create a `.env` file (copy from `.env.example`):

```bash
# Database
DATABASE_URL=postgresql+psycopg://rag:ragpw@localhost:5433/ragdb

# OpenAI (optional, for embeddings)
OPENAI_API_KEY=sk-proj-your-key-here

# Admin UI
FLASK_SECRET_KEY=generate-with-python-secrets-token-hex

# Typeform Integration (optional)
TYPEFORM_CLIENT_ID=your_typeform_client_id
TYPEFORM_CLIENT_SECRET=your_typeform_client_secret

# HubSpot Integration (optional)
HUBSPOT_CLIENT_ID=your_hubspot_client_id
HUBSPOT_CLIENT_SECRET=your_hubspot_client_secret

# Salesforce Integration (optional)
SALESFORCE_CLIENT_ID=your_salesforce_client_id
SALESFORCE_CLIENT_SECRET=your_salesforce_client_secret

# Google Calendar Integration (optional)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/google/callback

# Outlook Calendar Integration (optional)
OUTLOOK_CLIENT_ID=your-application-id
OUTLOOK_CLIENT_SECRET=your-client-secret-value
OUTLOOK_TENANT_ID=common
OUTLOOK_REDIRECT_URI=http://localhost:8000/oauth/outlook/callback
```

---

## What's Next?

### 1. Customize Your Knowledge Base

```bash
# Ingest your company docs
python app/ingest.py /path/to/your/docs/

# Ingest from URL
python app/ingest.py https://your-company.com/docs

# Query your KB
python app/query.py "Your question here"
```

### 2. Create Campaigns

1. Visit Admin UI: http://localhost:8000
2. Click "Manage Campaigns"
3. Create campaign with:
   - Trigger type (manual, scheduled, event)
   - CRM source (HubSpot or Salesforce)
   - Filters for importing contacts
   - Max prospects

### 3. Automate Meeting Booking

Integrate calendar booking into your agent workflows:

```python
from app.calendar_manager import quick_book_meeting

# In your SDR agent workflow
result = quick_book_meeting(
    user_id="sales_rep_001",
    customer_email=prospect_email,
    title=f"Demo - {company_name}",
    duration_minutes=30,
    description=personalized_message
)
```

### 4. Build Custom Workflows

See examples:
- `examples/sdr_workflow.py` - Complete SDR agent
- `examples/integration_workflow.py` - CRM integrations
- `examples/calendar_workflow.py` - Calendar operations

### 5. Production Deployment

Before deploying to production:

- [ ] Use HTTPS for all redirect URIs
- [ ] Store secrets in secure vault (not .env)
- [ ] Enable database connection pooling
- [ ] Set up monitoring and logging
- [ ] Configure rate limiting
- [ ] Review security checklist in docs

---

## Quick Reference Commands

```bash
# Start everything
docker compose up -d
source .venv/bin/activate
python app/admin_ui.py

# Ingest documents
python app/ingest.py your_file.pdf

# Query knowledge base
python app/query.py "your question"

# Run SDR agent
python examples/sdr_workflow.py

# Check database
psql $DATABASE_URL

# View logs
docker compose logs -f

# Stop everything
docker compose down
deactivate
```

---

## Getting Help

- **Documentation**: See `docs/` folder for detailed guides
  - `CRM_INTEGRATIONS.md` - CRM setup
  - `CALENDAR_INTEGRATIONS.md` - Calendar setup
  - `SDR_AGENT.md` - Agent configuration
  - `KNOWLEDGE_BASE_INTEGRATION.md` - KB guide

- **Examples**: See `examples/` folder for working code
  - `sdr_workflow.py` - SDR agent demo
  - `integration_workflow.py` - CRM examples
  - `calendar_workflow.py` - Calendar examples

- **Issues**: Check GitHub issues or create new one

---

## Success Checklist

- [ ] Database running (Docker)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Database schema created (all 3 SQL files)
- [ ] Basic RAG working (ingest + query)
- [ ] Admin UI accessible (http://localhost:8000)
- [ ] At least one CRM connected (optional)
- [ ] At least one calendar connected (optional)
- [ ] Can query knowledge base
- [ ] Can upload documents via UI
- [ ] Can check calendar availability (if connected)
- [ ] Can book test meeting (if connected)

**🎉 If all checked, you're ready to go!**

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Admin UI (Port 8000)                     │
│  • Document uploads          • Campaign management               │
│  • OAuth connections         • Calendar dashboard                │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│ CRM Module  │  │ Cal Module  │  │  RAG Engine  │
│ • Typeform  │  │ • Google    │  │ • Ingest     │
│ • HubSpot   │  │ • Outlook   │  │ • Query      │
│ • Salesforce│  │ • Booking   │  │ • Vectors    │
└──────┬──────┘  └──────┬──────┘  └──────┬───────┘
       │                │                 │
       └────────────────┼─────────────────┘
                        ▼
         ┌──────────────────────────────┐
         │   PostgreSQL + pgvector      │
         │  • Documents & Chunks         │
         │  • OAuth Tokens               │
         │  • CRM Sync Metadata          │
         │  • Calendar Events            │
         │  • Prospects & Campaigns      │
         └──────────────────────────────┘
```

---

**Ready to start?** Jump to [Quick Start](#quick-start-5-minutes)!
