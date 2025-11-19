"""
Microsoft Outlook Calendar Integration Module

Implements FR-CAL-001, FR-CAL-002, FR-CAL-003:
- OAuth 2.0 authentication with Microsoft Graph API
- Real-time availability checking via Outlook Calendar
- Automated meeting booking with attendees

Dependencies:
    pip install msal requests

Environment Variables:
    OUTLOOK_CLIENT_ID: Microsoft Azure AD application client ID
    OUTLOOK_CLIENT_SECRET: Microsoft Azure AD application client secret
    OUTLOOK_TENANT_ID: Microsoft Azure AD tenant ID (or 'common')
    OUTLOOK_REDIRECT_URI: OAuth redirect URI (default: http://localhost:8000/oauth/outlook/callback)
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlencode

import msal

from app.manage import get_db_connection


@dataclass
class CalendarEvent:
    """Represents a calendar event."""
    id: Optional[str]
    summary: str
    description: Optional[str]
    start: datetime
    end: datetime
    attendees: List[str]
    location: Optional[str] = None
    conferencing: Optional[Dict] = None


@dataclass
class TimeSlot:
    """Represents an available time slot."""
    start: datetime
    end: datetime
    duration_minutes: int


class OutlookCalendarOAuth:
    """Handles OAuth 2.0 authentication for Microsoft Graph API."""
    
    SCOPES = ['Calendars.ReadWrite', 'offline_access']
    AUTHORITY_BASE = "https://login.microsoftonline.com"
    
    def __init__(self):
        self.client_id = os.getenv('OUTLOOK_CLIENT_ID')
        self.client_secret = os.getenv('OUTLOOK_CLIENT_SECRET')
        self.tenant_id = os.getenv('OUTLOOK_TENANT_ID', 'common')
        self.redirect_uri = os.getenv('OUTLOOK_REDIRECT_URI', 'http://localhost:8000/oauth/outlook/callback')
        
        if not self.client_id or not self.client_secret:
            raise ValueError("OUTLOOK_CLIENT_ID and OUTLOOK_CLIENT_SECRET must be set")
        
        self.authority = f"{self.AUTHORITY_BASE}/{self.tenant_id}"
    
    def _get_msal_app(self):
        """Create MSAL confidential client application."""
        return msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Microsoft OAuth authorization URL.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL to redirect user to
        """
        app = self._get_msal_app()
        
        auth_url = app.get_authorization_request_url(
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri,
            state=state
        )
        
        return auth_url
    
    def exchange_code_for_token(self, code: str) -> Dict[str, str]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Dictionary with access_token, refresh_token, expires_in
        """
        app = self._get_msal_app()
        
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        if "error" in result:
            raise Exception(f"Token exchange failed: {result.get('error_description', result['error'])}")
        
        return {
            'access_token': result['access_token'],
            'refresh_token': result.get('refresh_token'),
            'expires_in': result.get('expires_in', 3600),
            'token_type': 'Bearer'
        }
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            Dictionary with new access_token and expires_in
        """
        app = self._get_msal_app()
        
        result = app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=self.SCOPES
        )
        
        if "error" in result:
            raise Exception(f"Token refresh failed: {result.get('error_description', result['error'])}")
        
        return {
            'access_token': result['access_token'],
            'refresh_token': result.get('refresh_token', refresh_token),
            'expires_in': result.get('expires_in', 3600)
        }
    
    def store_token(self, user_id: str, token_data: Dict[str, str]):
        """
        Store OAuth token in database.
        
        Args:
            user_id: User identifier
            token_data: Token data from exchange or refresh
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 3600))
        
        cur.execute("""
            INSERT INTO oauth_tokens (user_id, provider, access_token, refresh_token, expires_at)
            VALUES (%s, 'outlook_calendar', %s, %s, %s)
            ON CONFLICT (user_id, provider) 
            DO UPDATE SET 
                access_token = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token, oauth_tokens.refresh_token),
                expires_at = EXCLUDED.expires_at,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, token_data['access_token'], token_data.get('refresh_token'), expires_at))
        
        conn.commit()
        cur.close()
        conn.close()
    
    def get_token(self, user_id: str) -> Optional[Dict[str, str]]:
        """
        Retrieve and refresh token if needed.
        
        Args:
            user_id: User identifier
            
        Returns:
            Valid access token data or None
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT access_token, refresh_token, expires_at
            FROM oauth_tokens
            WHERE user_id = %s AND provider = 'outlook_calendar'
        """, (user_id,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            return None
        
        access_token, refresh_token, expires_at = row
        
        # Check if token is expired or about to expire (5 min buffer)
        if datetime.utcnow() >= expires_at - timedelta(minutes=5):
            if refresh_token:
                new_token = self.refresh_access_token(refresh_token)
                self.store_token(user_id, new_token)
                return new_token
            return None
        
        return {'access_token': access_token}


class OutlookCalendarClient:
    """Client for Microsoft Graph Calendar API operations."""
    
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, access_token: str):
        """
        Initialize Outlook Calendar client.
        
        Args:
            access_token: Valid OAuth access token
        """
        self.access_token = access_token
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        self.calendar_id = None  # None means default calendar
    
    def set_calendar(self, calendar_id: str):
        """Set the calendar to use for operations."""
        self.calendar_id = calendar_id
    
    def _get_calendar_path(self) -> str:
        """Get the API path for the current calendar."""
        if self.calendar_id:
            return f"/me/calendars/{self.calendar_id}"
        return "/me/calendar"
    
    def list_calendars(self) -> List[Dict]:
        """
        List all calendars accessible to the user.
        
        Returns:
            List of calendar dictionaries
        """
        url = f"{self.GRAPH_API_BASE}/me/calendars"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get('value', [])
        except requests.RequestException as e:
            print(f"Error listing calendars: {e}")
            return []
    
    def get_schedule(self, start: datetime, end: datetime, emails: List[str] = None) -> Dict:
        """
        Get schedule/free-busy information.
        
        Args:
            start: Start of time range
            end: End of time range
            emails: List of email addresses to check (default: current user)
            
        Returns:
            Schedule data from Microsoft Graph
        """
        url = f"{self.GRAPH_API_BASE}/me/calendar/getSchedule"
        
        if not emails:
            # Get current user's email
            me_url = f"{self.GRAPH_API_BASE}/me"
            me_response = requests.get(me_url, headers=self.headers)
            emails = [me_response.json().get('mail', me_response.json().get('userPrincipalName'))]
        
        body = {
            "schedules": emails,
            "startTime": {
                "dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC"
            },
            "endTime": {
                "dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC"
            },
            "availabilityViewInterval": 30  # 30-minute intervals
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=body)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error getting schedule: {e}")
            return {}
    
    def get_busy_times(self, start: datetime, end: datetime) -> List[Tuple[datetime, datetime]]:
        """
        Get busy time slots in the specified range.
        
        Args:
            start: Start of time range
            end: End of time range
            
        Returns:
            List of (start, end) tuples for busy periods
        """
        schedule_data = self.get_schedule(start, end)
        busy_periods = []
        
        for schedule in schedule_data.get('value', []):
            for item in schedule.get('scheduleItems', []):
                if item.get('status') in ['busy', 'tentative', 'oof', 'workingElsewhere']:
                    item_start = datetime.fromisoformat(item['start']['dateTime'])
                    item_end = datetime.fromisoformat(item['end']['dateTime'])
                    busy_periods.append((item_start, item_end))
        
        return busy_periods
    
    def find_available_slots(
        self,
        start: datetime,
        end: datetime,
        duration_minutes: int = 30,
        buffer_minutes: int = 0
    ) -> List[TimeSlot]:
        """
        Find available time slots within a date range.
        
        Args:
            start: Start of search range
            end: End of search range
            duration_minutes: Required duration for each slot
            buffer_minutes: Buffer time between meetings
            
        Returns:
            List of available TimeSlot objects
        """
        busy_times = self.get_busy_times(start, end)
        available_slots = []
        
        current = start
        slot_duration = timedelta(minutes=duration_minutes)
        buffer = timedelta(minutes=buffer_minutes)
        
        # Sort busy times by start time
        busy_times.sort(key=lambda x: x[0])
        
        for busy_start, busy_end in busy_times:
            # Check if there's a slot before this busy period
            while current + slot_duration <= busy_start:
                available_slots.append(TimeSlot(
                    start=current,
                    end=current + slot_duration,
                    duration_minutes=duration_minutes
                ))
                current += slot_duration
            
            # Move past the busy period with buffer
            current = max(current, busy_end + buffer)
        
        # Check remaining time after last busy period
        while current + slot_duration <= end:
            available_slots.append(TimeSlot(
                start=current,
                end=current + slot_duration,
                duration_minutes=duration_minutes
            ))
            current += slot_duration
        
        return available_slots
    
    def create_event(self, event: CalendarEvent) -> Optional[str]:
        """
        Create a calendar event.
        
        Args:
            event: CalendarEvent object with event details
            
        Returns:
            Event ID if successful, None otherwise
        """
        url = f"{self.GRAPH_API_BASE}{self._get_calendar_path()}/events"
        
        event_body = {
            'subject': event.summary,
            'body': {
                'contentType': 'HTML',
                'content': event.description or ''
            },
            'start': {
                'dateTime': event.start.strftime("%Y-%m-%dT%H:%M:%S"),
                'timeZone': 'UTC'
            },
            'end': {
                'dateTime': event.end.strftime("%Y-%m-%dT%H:%M:%S"),
                'timeZone': 'UTC'
            },
            'attendees': [
                {
                    'emailAddress': {'address': email},
                    'type': 'required'
                }
                for email in event.attendees
            ]
        }
        
        if event.location:
            event_body['location'] = {'displayName': event.location}
        
        if event.conferencing:
            event_body['isOnlineMeeting'] = True
            event_body['onlineMeetingProvider'] = 'teamsForBusiness'
        
        try:
            response = requests.post(url, headers=self.headers, json=event_body)
            response.raise_for_status()
            created_event = response.json()
            return created_event['id']
        except requests.RequestException as e:
            print(f"Error creating event: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            return None
    
    def get_event(self, event_id: str) -> Optional[Dict]:
        """
        Retrieve a calendar event by ID.
        
        Args:
            event_id: Outlook Calendar event ID
            
        Returns:
            Event data or None
        """
        url = f"{self.GRAPH_API_BASE}{self._get_calendar_path()}/events/{event_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error getting event: {e}")
            return None
    
    def update_event(self, event_id: str, updates: Dict) -> bool:
        """
        Update a calendar event.
        
        Args:
            event_id: Event ID to update
            updates: Dictionary of fields to update (Graph API format)
            
        Returns:
            True if successful
        """
        url = f"{self.GRAPH_API_BASE}{self._get_calendar_path()}/events/{event_id}"
        
        try:
            response = requests.patch(url, headers=self.headers, json=updates)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Error updating event: {e}")
            return False
    
    def cancel_event(self, event_id: str, comment: str = None) -> bool:
        """
        Cancel (delete) a calendar event.
        
        Args:
            event_id: Event ID to cancel
            comment: Optional cancellation message
            
        Returns:
            True if successful
        """
        url = f"{self.GRAPH_API_BASE}{self._get_calendar_path()}/events/{event_id}/cancel"
        
        body = {}
        if comment:
            body['comment'] = comment
        
        try:
            response = requests.post(url, headers=self.headers, json=body)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Error canceling event: {e}")
            return False
    
    def find_meeting_times(
        self,
        attendees: List[str],
        duration_minutes: int,
        start: datetime,
        end: datetime,
        max_candidates: int = 5
    ) -> List[TimeSlot]:
        """
        Use Microsoft's findMeetingTimes API to suggest meeting times.
        
        Args:
            attendees: List of attendee email addresses
            duration_minutes: Meeting duration
            start: Earliest possible start time
            end: Latest possible start time
            max_candidates: Maximum number of suggestions
            
        Returns:
            List of suggested TimeSlot objects
        """
        url = f"{self.GRAPH_API_BASE}/me/findMeetingTimes"
        
        body = {
            "attendees": [
                {
                    "emailAddress": {"address": email},
                    "type": "required"
                }
                for email in attendees
            ],
            "timeConstraint": {
                "timeslots": [
                    {
                        "start": {
                            "dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                            "timeZone": "UTC"
                        },
                        "end": {
                            "dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"),
                            "timeZone": "UTC"
                        }
                    }
                ]
            },
            "meetingDuration": f"PT{duration_minutes}M",
            "maxCandidates": max_candidates,
            "returnSuggestionReasons": True
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=body)
            response.raise_for_status()
            result = response.json()
            
            suggestions = []
            for meeting_time in result.get('meetingTimeSuggestions', []):
                time_slot = meeting_time['meetingTimeSlot']
                slot_start = datetime.fromisoformat(time_slot['start']['dateTime'])
                slot_end = datetime.fromisoformat(time_slot['end']['dateTime'])
                
                suggestions.append(TimeSlot(
                    start=slot_start,
                    end=slot_end,
                    duration_minutes=duration_minutes
                ))
            
            return suggestions
        except requests.RequestException as e:
            print(f"Error finding meeting times: {e}")
            return []


# Convenience functions for common workflows

def authenticate_outlook_calendar(user_id: str) -> str:
    """
    Start Outlook Calendar OAuth flow.
    
    Args:
        user_id: User identifier for state tracking
        
    Returns:
        Authorization URL to redirect user to
    """
    oauth = OutlookCalendarOAuth()
    return oauth.get_authorization_url(state=user_id)


def complete_outlook_calendar_oauth(user_id: str, code: str):
    """
    Complete Outlook Calendar OAuth flow.
    
    Args:
        user_id: User identifier
        code: Authorization code from callback
    """
    oauth = OutlookCalendarOAuth()
    token_data = oauth.exchange_code_for_token(code)
    oauth.store_token(user_id, token_data)


def get_calendar_client(user_id: str) -> Optional[OutlookCalendarClient]:
    """
    Get authenticated Outlook Calendar client for user.
    
    Args:
        user_id: User identifier
        
    Returns:
        OutlookCalendarClient or None if not authenticated
    """
    oauth = OutlookCalendarOAuth()
    token_data = oauth.get_token(user_id)
    
    if not token_data:
        return None
    
    return OutlookCalendarClient(token_data['access_token'])


def check_availability(
    user_id: str,
    start: datetime,
    end: datetime,
    duration_minutes: int = 30
) -> List[TimeSlot]:
    """
    Check calendar availability and return available slots.
    
    Implements FR-CAL-002: Real-time availability checking.
    
    Args:
        user_id: User whose calendar to check
        start: Start of time range
        end: End of time range
        duration_minutes: Required meeting duration
        
    Returns:
        List of available TimeSlot objects
    """
    client = get_calendar_client(user_id)
    if not client:
        raise ValueError(f"User {user_id} not authenticated with Outlook Calendar")
    
    return client.find_available_slots(start, end, duration_minutes)


def book_meeting(
    user_id: str,
    title: str,
    start: datetime,
    end: datetime,
    attendee_emails: List[str],
    description: Optional[str] = None,
    location: Optional[str] = None,
    add_teams_meeting: bool = True
) -> Optional[str]:
    """
    Book a meeting in the calendar.
    
    Implements FR-CAL-003: Automated meeting booking with attendees.
    
    Args:
        user_id: User whose calendar to book in
        title: Meeting title
        start: Meeting start time
        end: Meeting end time
        attendee_emails: List of attendee email addresses
        description: Optional meeting description
        location: Optional location
        add_teams_meeting: Whether to add Microsoft Teams meeting
        
    Returns:
        Event ID if successful, None otherwise
    """
    client = get_calendar_client(user_id)
    if not client:
        raise ValueError(f"User {user_id} not authenticated with Outlook Calendar")
    
    conferencing = {'enabled': True} if add_teams_meeting else None
    
    event = CalendarEvent(
        id=None,
        summary=title,
        description=description,
        start=start,
        end=end,
        attendees=attendee_emails,
        location=location,
        conferencing=conferencing
    )
    
    event_id = client.create_event(event)
    
    # Store in database for tracking
    if event_id:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO calendar_events (user_id, provider, event_id, title, start_time, end_time, attendees, created_at)
            VALUES (%s, 'outlook', %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (user_id, event_id, title, start, end, json.dumps(attendee_emails)))
        conn.commit()
        cur.close()
        conn.close()
    
    return event_id
