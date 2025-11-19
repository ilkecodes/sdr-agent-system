"""
Google Calendar Integration Module

Implements FR-CAL-001, FR-CAL-002, FR-CAL-003:
- OAuth 2.0 authentication with Google Calendar API
- Real-time availability checking
- Automated meeting booking with attendees

Dependencies:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

Environment Variables:
    GOOGLE_CLIENT_ID: Google OAuth client ID
    GOOGLE_CLIENT_SECRET: Google OAuth client secret
    GOOGLE_REDIRECT_URI: OAuth redirect URI (default: http://localhost:8000/oauth/google/callback)
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlencode

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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


class GoogleCalendarOAuth:
    """Handles OAuth 2.0 authentication for Google Calendar API."""
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    def __init__(self):
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8000/oauth/google/callback')
        
        if not self.client_id or not self.client_secret:
            raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Google OAuth authorization URL.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL to redirect user to
        """
        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'
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
        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        return {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'expires_in': 3600,  # Google tokens typically expire in 1 hour
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
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        request = Request()
        credentials.refresh(request)
        
        return {
            'access_token': credentials.token,
            'expires_in': 3600
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
            VALUES (%s, 'google_calendar', %s, %s, %s)
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
            WHERE user_id = %s AND provider = 'google_calendar'
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


class GoogleCalendarClient:
    """Client for Google Calendar API operations."""
    
    def __init__(self, access_token: str):
        """
        Initialize Google Calendar client.
        
        Args:
            access_token: Valid OAuth access token
        """
        credentials = Credentials(token=access_token)
        self.service = build('calendar', 'v3', credentials=credentials)
        self.calendar_id = 'primary'  # Default to primary calendar
    
    def set_calendar(self, calendar_id: str):
        """Set the calendar to use for operations."""
        self.calendar_id = calendar_id
    
    def list_calendars(self) -> List[Dict]:
        """
        List all calendars accessible to the user.
        
        Returns:
            List of calendar dictionaries
        """
        try:
            calendars = self.service.calendarList().list().execute()
            return calendars.get('items', [])
        except HttpError as e:
            print(f"Error listing calendars: {e}")
            return []
    
    def get_busy_times(self, start: datetime, end: datetime) -> List[Tuple[datetime, datetime]]:
        """
        Get busy time slots in the specified range.
        
        Args:
            start: Start of time range
            end: End of time range
            
        Returns:
            List of (start, end) tuples for busy periods
        """
        try:
            body = {
                "timeMin": start.isoformat() + 'Z',
                "timeMax": end.isoformat() + 'Z',
                "items": [{"id": self.calendar_id}]
            }
            
            result = self.service.freebusy().query(body=body).execute()
            busy_periods = result['calendars'][self.calendar_id].get('busy', [])
            
            return [
                (
                    datetime.fromisoformat(period['start'].replace('Z', '+00:00')),
                    datetime.fromisoformat(period['end'].replace('Z', '+00:00'))
                )
                for period in busy_periods
            ]
        except HttpError as e:
            print(f"Error getting busy times: {e}")
            return []
    
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
        event_body = {
            'summary': event.summary,
            'description': event.description,
            'start': {
                'dateTime': event.start.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': event.end.isoformat(),
                'timeZone': 'UTC',
            },
            'attendees': [{'email': email} for email in event.attendees],
        }
        
        if event.location:
            event_body['location'] = event.location
        
        if event.conferencing:
            event_body['conferenceData'] = event.conferencing
            # Request conference creation
            conference_version = 1
        else:
            conference_version = 0
        
        try:
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event_body,
                conferenceDataVersion=conference_version,
                sendUpdates='all'  # Send email notifications to attendees
            ).execute()
            
            return created_event['id']
        except HttpError as e:
            print(f"Error creating event: {e}")
            return None
    
    def get_event(self, event_id: str) -> Optional[Dict]:
        """
        Retrieve a calendar event by ID.
        
        Args:
            event_id: Google Calendar event ID
            
        Returns:
            Event data or None
        """
        try:
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            return event
        except HttpError as e:
            print(f"Error getting event: {e}")
            return None
    
    def update_event(self, event_id: str, updates: Dict) -> bool:
        """
        Update a calendar event.
        
        Args:
            event_id: Event ID to update
            updates: Dictionary of fields to update
            
        Returns:
            True if successful
        """
        try:
            event = self.get_event(event_id)
            if not event:
                return False
            
            event.update(updates)
            
            self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            return True
        except HttpError as e:
            print(f"Error updating event: {e}")
            return False
    
    def cancel_event(self, event_id: str) -> bool:
        """
        Cancel (delete) a calendar event.
        
        Args:
            event_id: Event ID to cancel
            
        Returns:
            True if successful
        """
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id,
                sendUpdates='all'
            ).execute()
            return True
        except HttpError as e:
            print(f"Error canceling event: {e}")
            return False


# Convenience functions for common workflows

def authenticate_google_calendar(user_id: str) -> str:
    """
    Start Google Calendar OAuth flow.
    
    Args:
        user_id: User identifier for state tracking
        
    Returns:
        Authorization URL to redirect user to
    """
    oauth = GoogleCalendarOAuth()
    return oauth.get_authorization_url(state=user_id)


def complete_google_calendar_oauth(user_id: str, code: str):
    """
    Complete Google Calendar OAuth flow.
    
    Args:
        user_id: User identifier
        code: Authorization code from callback
    """
    oauth = GoogleCalendarOAuth()
    token_data = oauth.exchange_code_for_token(code)
    oauth.store_token(user_id, token_data)


def get_calendar_client(user_id: str) -> Optional[GoogleCalendarClient]:
    """
    Get authenticated Google Calendar client for user.
    
    Args:
        user_id: User identifier
        
    Returns:
        GoogleCalendarClient or None if not authenticated
    """
    oauth = GoogleCalendarOAuth()
    token_data = oauth.get_token(user_id)
    
    if not token_data:
        return None
    
    return GoogleCalendarClient(token_data['access_token'])


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
        raise ValueError(f"User {user_id} not authenticated with Google Calendar")
    
    return client.find_available_slots(start, end, duration_minutes)


def book_meeting(
    user_id: str,
    title: str,
    start: datetime,
    end: datetime,
    attendee_emails: List[str],
    description: Optional[str] = None,
    location: Optional[str] = None,
    add_google_meet: bool = True
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
        add_google_meet: Whether to add Google Meet conferencing
        
    Returns:
        Event ID if successful, None otherwise
    """
    client = get_calendar_client(user_id)
    if not client:
        raise ValueError(f"User {user_id} not authenticated with Google Calendar")
    
    conferencing = None
    if add_google_meet:
        conferencing = {
            'createRequest': {
                'requestId': f"{user_id}-{int(datetime.utcnow().timestamp())}",
                'conferenceSolutionKey': {'type': 'hangoutsMeet'}
            }
        }
    
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
            VALUES (%s, 'google', %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (user_id, event_id, title, start, end, json.dumps(attendee_emails)))
        conn.commit()
        cur.close()
        conn.close()
    
    return event_id
