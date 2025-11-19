# Calendar Integration Guide

Complete guide for integrating Google Calendar and Microsoft Outlook Calendar with the SDR Agent System. This integration enables real-time availability checking and automated meeting booking with prospects.

---

## Table of Contents

- [Requirements Satisfied](#requirements-satisfied)
- [Overview](#overview)
- [Setup](#setup)
  - [Google Calendar Setup](#google-calendar-setup)
  - [Microsoft Outlook Calendar Setup](#microsoft-outlook-calendar-setup)
- [Database Schema](#database-schema)
- [Usage](#usage)
  - [OAuth Authentication](#oauth-authentication)
  - [Check Availability](#check-availability)
  - [Book Meetings](#book-meetings)
  - [Unified Calendar Manager](#unified-calendar-manager)
- [SDR Agent Integration](#sdr-agent-integration)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Production Checklist](#production-checklist)

---

## Requirements Satisfied

This integration satisfies the following functional requirements:

| Requirement | Description | Implementation |
|------------|-------------|----------------|
| **FR-CAL-001** | System shall integrate with Google Calendar and Microsoft Outlook Calendar APIs | ✅ OAuth 2.0 authentication for both providers in `google_calendar_integration.py` and `outlook_calendar_integration.py` |
| **FR-CAL-002** | AI agent shall query designated calendar for available slots in real-time | ✅ Real-time availability checking via `check_availability()` and `find_available_slots()` methods |
| **FR-CAL-003** | System shall book meetings in designated calendar with customer as attendee | ✅ Automated meeting booking via `book_meeting()` with email invitations and conferencing links |

---

## Overview

The calendar integration system provides:

- **Multi-provider support**: Works with both Google Calendar and Microsoft Outlook Calendar
- **OAuth 2.0 authentication**: Secure, token-based authentication with automatic refresh
- **Real-time availability**: Query free/busy status and find available time slots
- **Automated booking**: Create meetings with attendees, locations, and video conferencing
- **Unified interface**: Provider-agnostic `CalendarManager` for seamless integration
- **Database tracking**: Store OAuth tokens and track booked meetings

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SDR Agent / Admin UI                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              CalendarManager (Unified Interface)             │
│  - Auto-detect provider                                      │
│  - check_availability()                                      │
│  - book_meeting()                                            │
│  - propose_meeting_times()                                   │
└──────────┬────────────────────────────┬─────────────────────┘
           │                            │
           ▼                            ▼
┌──────────────────────┐    ┌──────────────────────────┐
│ GoogleCalendarClient │    │ OutlookCalendarClient    │
│ - OAuth 2.0          │    │ - OAuth 2.0 (MSAL)       │
│ - Free/busy API      │    │ - GetSchedule API        │
│ - Events API         │    │ - Graph Events API       │
└──────────┬───────────┘    └────────┬─────────────────┘
           │                         │
           ▼                         ▼
┌──────────────────────┐    ┌──────────────────────────┐
│  Google Calendar API │    │  Microsoft Graph API     │
└──────────────────────┘    └──────────────────────────┘
```

---

## Setup

### Google Calendar Setup

#### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Calendar API:
   - Navigate to **APIs & Services** > **Library**
   - Search for "Google Calendar API"
   - Click **Enable**

#### 2. Create OAuth 2.0 Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Configure OAuth consent screen if prompted:
   - User Type: **External** (or Internal for workspace)
   - Add scopes: `https://www.googleapis.com/auth/calendar`
4. Application type: **Web application**
5. Add authorized redirect URI:
   - For development: `http://localhost:8000/oauth/google/callback`
   - For production: `https://yourdomain.com/oauth/google/callback`
6. Save and note the **Client ID** and **Client Secret**

#### 3. Set Environment Variables

```bash
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-client-secret"
export GOOGLE_REDIRECT_URI="http://localhost:8000/oauth/google/callback"
```

Add to `.env`:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/google/callback
```

---

### Microsoft Outlook Calendar Setup

#### 1. Register Azure AD Application

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Configure:
   - Name: "SDR Agent Calendar Integration"
   - Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
   - Redirect URI: **Web** - `http://localhost:8000/oauth/outlook/callback`
5. Click **Register**

#### 2. Configure API Permissions

1. In your app registration, go to **API permissions**
2. Click **Add a permission** > **Microsoft Graph** > **Delegated permissions**
3. Add these permissions:
   - `Calendars.ReadWrite`
   - `offline_access`
4. Click **Grant admin consent** (if you have admin rights)

#### 3. Create Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Add description and expiration
4. Copy the **Value** (this is your client secret - you can't see it again!)

#### 4. Set Environment Variables

```bash
export OUTLOOK_CLIENT_ID="your-application-id"
export OUTLOOK_CLIENT_SECRET="your-client-secret-value"
export OUTLOOK_TENANT_ID="common"  # or your specific tenant ID
export OUTLOOK_REDIRECT_URI="http://localhost:8000/oauth/outlook/callback"
```

Add to `.env`:

```env
OUTLOOK_CLIENT_ID=your-application-id
OUTLOOK_CLIENT_SECRET=your-client-secret-value
OUTLOOK_TENANT_ID=common
OUTLOOK_REDIRECT_URI=http://localhost:8000/oauth/outlook/callback
```

---

## Database Schema

The calendar integration adds a `calendar_events` table to track booked meetings:

```sql
CREATE TABLE calendar_events (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,  -- 'google', 'outlook'
    event_id VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    attendees JSONB DEFAULT '[]',
    location TEXT,
    description TEXT,
    conferencing_link TEXT,
    status VARCHAR(50) DEFAULT 'confirmed',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, provider, event_id)
);
```

OAuth tokens are stored in the existing `oauth_tokens` table with providers `'google_calendar'` and `'outlook_calendar'`.

---

## Usage

### OAuth Authentication

#### Google Calendar

```python
from app.google_calendar_integration import authenticate_google_calendar, complete_google_calendar_oauth

# Step 1: Get authorization URL
user_id = "sales_rep_123"
auth_url = authenticate_google_calendar(user_id)
print(f"Visit: {auth_url}")

# Step 2: After user authorizes, exchange code for token
authorization_code = "4/0AfJohXm..."  # From callback
complete_google_calendar_oauth(user_id, authorization_code)
```

#### Microsoft Outlook

```python
from app.outlook_calendar_integration import authenticate_outlook_calendar, complete_outlook_calendar_oauth

# Step 1: Get authorization URL
user_id = "sales_rep_123"
auth_url = authenticate_outlook_calendar(user_id)
print(f"Visit: {auth_url}")

# Step 2: After user authorizes, exchange code for token
authorization_code = "M.C507_BAY..."  # From callback
complete_outlook_calendar_oauth(user_id, authorization_code)
```

---

### Check Availability

#### Google Calendar

```python
from app.google_calendar_integration import check_availability
from datetime import datetime, timedelta

user_id = "sales_rep_123"
start = datetime.utcnow()
end = start + timedelta(days=7)

# Get 30-minute slots
available_slots = check_availability(user_id, start, end, duration_minutes=30)

for slot in available_slots:
    print(f"Available: {slot.start} to {slot.end}")
```

#### Microsoft Outlook

```python
from app.outlook_calendar_integration import check_availability
from datetime import datetime, timedelta

user_id = "sales_rep_123"
start = datetime.utcnow()
end = start + timedelta(days=7)

# Get 30-minute slots
available_slots = check_availability(user_id, start, end, duration_minutes=30)

for slot in available_slots:
    print(f"Available: {slot.start} to {slot.end}")
```

---

### Book Meetings

#### Google Calendar (with Google Meet)

```python
from app.google_calendar_integration import book_meeting
from datetime import datetime, timedelta

user_id = "sales_rep_123"
start = datetime(2025, 11, 20, 14, 0)  # 2 PM UTC
end = start + timedelta(minutes=30)

event_id = book_meeting(
    user_id=user_id,
    title="Product Demo with Acme Corp",
    start=start,
    end=end,
    attendee_emails=["customer@acmecorp.com"],
    description="Demo of our enterprise features",
    add_google_meet=True  # Adds Google Meet link
)

print(f"Meeting booked! Event ID: {event_id}")
```

#### Microsoft Outlook (with Teams)

```python
from app.outlook_calendar_integration import book_meeting
from datetime import datetime, timedelta

user_id = "sales_rep_123"
start = datetime(2025, 11, 20, 14, 0)
end = start + timedelta(minutes=30)

event_id = book_meeting(
    user_id=user_id,
    title="Product Demo with Acme Corp",
    start=start,
    end=end,
    attendee_emails=["customer@acmecorp.com"],
    description="Demo of our enterprise features",
    add_teams_meeting=True  # Adds Microsoft Teams link
)

print(f"Meeting booked! Event ID: {event_id}")
```

---

### Unified Calendar Manager

The `CalendarManager` provides a provider-agnostic interface:

```python
from app.calendar_manager import CalendarManager, CalendarProvider
from datetime import datetime, timedelta

# Auto-detect provider or specify explicitly
manager = CalendarManager("sales_rep_123")
# OR
manager = CalendarManager("sales_rep_123", provider=CalendarProvider.GOOGLE)

# Check if authenticated
if not manager.is_authenticated():
    auth_url = manager.start_oauth_flow()
    print(f"Please authenticate: {auth_url}")
    # After callback:
    manager.complete_oauth_flow(authorization_code)

# Check availability
start = datetime.utcnow()
end = start + timedelta(days=7)
slots = manager.check_availability(start, end, duration_minutes=30)

# Find next available slot
next_slot = manager.find_next_available_slot(
    duration_minutes=30,
    days_ahead=7,
    working_hours_only=True
)

if next_slot:
    print(f"Next available: {next_slot.start}")
    
    # Book a meeting
    event_id = manager.book_meeting(
        title="Discovery Call",
        start=next_slot.start,
        end=next_slot.end,
        attendee_emails=["prospect@company.com"],
        description="Initial discovery call",
        add_video_conferencing=True
    )
    print(f"Booked: {event_id}")
```

---

## SDR Agent Integration

### Quick Meeting Booking

```python
from app.calendar_manager import quick_book_meeting

# Automatically finds next available slot and books
result = quick_book_meeting(
    user_id="sales_rep_123",
    customer_email="prospect@company.com",
    title="Product Demo",
    duration_minutes=30,
    description="Personalized demo of our platform"
)

if result:
    print(f"Meeting booked for {result['start_time']}")
    print(f"Provider: {result['provider']}")
    print(f"Event ID: {result['event_id']}")
else:
    print("No available slots found")
```

### Propose Multiple Times

```python
from app.calendar_manager import CalendarManager

manager = CalendarManager("sales_rep_123")

# Propose 3 meeting time options
proposals = manager.propose_meeting_times(
    attendee_emails=["prospect@company.com"],
    duration_minutes=30,
    num_options=3,
    days_ahead=7,
    working_hours_only=True
)

print("Proposed meeting times:")
for i, slot in enumerate(proposals, 1):
    print(f"{i}. {slot.start.strftime('%A, %B %d at %I:%M %p')}")
```

### Integration with SDR Agent Tools

```python
# In app/tools.py or agent workflow

from app.calendar_manager import CalendarManager, quick_book_meeting

class CalendarTools:
    """Calendar tools for SDR agent."""
    
    @staticmethod
    def check_rep_availability(rep_id: str, days_ahead: int = 7):
        """Check sales rep availability."""
        manager = CalendarManager(rep_id)
        
        next_slot = manager.find_next_available_slot(
            duration_minutes=30,
            days_ahead=days_ahead,
            working_hours_only=True
        )
        
        if next_slot:
            return {
                "available": True,
                "next_slot": next_slot.start.isoformat(),
                "duration_minutes": next_slot.duration_minutes
            }
        return {"available": False}
    
    @staticmethod
    def book_demo(rep_id: str, prospect_email: str, title: str = "Product Demo"):
        """Book a demo meeting."""
        result = quick_book_meeting(
            user_id=rep_id,
            customer_email=prospect_email,
            title=title,
            duration_minutes=30,
            description="Personalized product demonstration"
        )
        
        return result
```

---

## API Reference

### GoogleCalendarClient

```python
class GoogleCalendarClient:
    def __init__(self, access_token: str)
    def list_calendars(self) -> List[Dict]
    def get_busy_times(self, start: datetime, end: datetime) -> List[Tuple[datetime, datetime]]
    def find_available_slots(self, start: datetime, end: datetime, duration_minutes: int, buffer_minutes: int) -> List[TimeSlot]
    def create_event(self, event: CalendarEvent) -> Optional[str]
    def get_event(self, event_id: str) -> Optional[Dict]
    def update_event(self, event_id: str, updates: Dict) -> bool
    def cancel_event(self, event_id: str) -> bool
```

### OutlookCalendarClient

```python
class OutlookCalendarClient:
    def __init__(self, access_token: str)
    def list_calendars(self) -> List[Dict]
    def get_schedule(self, start: datetime, end: datetime, emails: List[str]) -> Dict
    def get_busy_times(self, start: datetime, end: datetime) -> List[Tuple[datetime, datetime]]
    def find_available_slots(self, start: datetime, end: datetime, duration_minutes: int, buffer_minutes: int) -> List[TimeSlot]
    def create_event(self, event: CalendarEvent) -> Optional[str]
    def find_meeting_times(self, attendees: List[str], duration_minutes: int, start: datetime, end: datetime, max_candidates: int) -> List[TimeSlot]
    def cancel_event(self, event_id: str, comment: str) -> bool
```

### CalendarManager

```python
class CalendarManager:
    def __init__(self, user_id: str, provider: Optional[CalendarProvider] = None)
    def start_oauth_flow(self) -> str
    def complete_oauth_flow(self, code: str)
    def is_authenticated(self) -> bool
    def check_availability(self, start: datetime, end: datetime, duration_minutes: int) -> List[TimeSlot]
    def find_next_available_slot(self, duration_minutes: int, days_ahead: int, working_hours_only: bool) -> Optional[TimeSlot]
    def book_meeting(self, title: str, start: datetime, end: datetime, attendee_emails: List[str], ...) -> Optional[str]
    def get_upcoming_meetings(self, days_ahead: int) -> List[Dict]
    def propose_meeting_times(self, attendee_emails: List[str], duration_minutes: int, num_options: int, days_ahead: int) -> List[TimeSlot]
```

---

## Examples

See [`examples/calendar_workflow.py`](../examples/calendar_workflow.py) for complete working examples.

---

## Troubleshooting

### Google Calendar Issues

**Error: "invalid_grant" during token exchange**
- Your authorization code has expired (they expire quickly)
- Re-initiate the OAuth flow

**Error: "insufficient_scope"**
- Ensure `https://www.googleapis.com/auth/calendar` scope is requested
- Re-authorize with `prompt=consent` to force scope approval

**No events created despite success response**
- Check that user has granted calendar permissions
- Verify calendar ID is correct (try `'primary'`)

### Microsoft Outlook Issues

**Error: "AADSTS65001: The user or administrator has not consented"**
- Admin consent required for organization
- Have tenant admin grant consent in Azure Portal

**Error: "InvalidAuthenticationToken"**
- Token has expired - refresh mechanism should handle this
- Check system clock is synchronized

**Error: "The specified object was not found"**
- Calendar ID is incorrect
- Use `list_calendars()` to find the correct ID

### General Issues

**Token refresh failures**
- Refresh tokens can be revoked by user
- Re-authenticate user through OAuth flow

**Timezone issues**
- All times should be in UTC
- Calendar APIs handle timezone conversion

**Rate limiting**
- Google: 1,000,000 requests/day
- Microsoft: Variable based on license
- Implement exponential backoff

---

## Production Checklist

### Security

- [ ] Store OAuth tokens encrypted at rest
- [ ] Use HTTPS for all redirect URIs
- [ ] Implement CSRF protection with state parameter
- [ ] Rotate client secrets regularly
- [ ] Never log access tokens or refresh tokens
- [ ] Implement token revocation on user logout

### Reliability

- [ ] Implement retry logic with exponential backoff
- [ ] Handle token refresh failures gracefully
- [ ] Log all calendar operations for audit trail
- [ ] Monitor API quota usage
- [ ] Set up alerts for authentication failures
- [ ] Test with multiple timezones

### Compliance

- [ ] Obtain user consent for calendar access
- [ ] Provide clear privacy policy
- [ ] Allow users to revoke calendar access
- [ ] Comply with Google API Services User Data Policy
- [ ] Comply with Microsoft API Terms of Use
- [ ] Implement data retention policies

### Performance

- [ ] Cache busy/free data (with short TTL)
- [ ] Batch availability checks when possible
- [ ] Use webhooks for calendar change notifications (advanced)
- [ ] Implement connection pooling
- [ ] Monitor response times

### User Experience

- [ ] Provide clear error messages
- [ ] Show calendar sync status in UI
- [ ] Allow users to choose preferred calendar provider
- [ ] Display conferencing links prominently
- [ ] Send confirmation emails after booking
- [ ] Handle calendar conflicts gracefully

---

## Additional Resources

- [Google Calendar API Documentation](https://developers.google.com/calendar/api)
- [Microsoft Graph Calendar Documentation](https://learn.microsoft.com/en-us/graph/api/resources/calendar)
- [OAuth 2.0 Best Practices](https://tools.ietf.org/html/rfc6749)
- [Google API Python Client](https://github.com/googleapis/google-api-python-client)
- [MSAL for Python](https://github.com/AzureAD/microsoft-authentication-library-for-python)
