"""
Unified Calendar Manager

Provides a provider-agnostic interface for calendar operations across
Google Calendar and Microsoft Outlook. Implements FR-CAL-001, FR-CAL-002, FR-CAL-003.

This module allows the system to work with either calendar provider seamlessly,
enabling real-time availability checks and automated meeting booking regardless
of which calendar service the user prefers.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from enum import Enum

from app.google_calendar_integration import (
    GoogleCalendarClient,
    authenticate_google_calendar,
    complete_google_calendar_oauth,
    get_calendar_client as get_google_client,
    check_availability as check_google_availability,
    book_meeting as book_google_meeting,
    TimeSlot as GoogleTimeSlot,
    CalendarEvent as GoogleCalendarEvent
)

from app.outlook_calendar_integration import (
    OutlookCalendarClient,
    authenticate_outlook_calendar,
    complete_outlook_calendar_oauth,
    get_calendar_client as get_outlook_client,
    check_availability as check_outlook_availability,
    book_meeting as book_outlook_meeting,
    TimeSlot as OutlookTimeSlot,
    CalendarEvent as OutlookCalendarEvent
)

from app.manage import get_db_connection


class CalendarProvider(Enum):
    """Supported calendar providers."""
    GOOGLE = "google"
    OUTLOOK = "outlook"


@dataclass
class TimeSlot:
    """Unified time slot representation."""
    start: datetime
    end: datetime
    duration_minutes: int


@dataclass
class CalendarEvent:
    """Unified calendar event representation."""
    id: Optional[str]
    summary: str
    description: Optional[str]
    start: datetime
    end: datetime
    attendees: List[str]
    location: Optional[str] = None
    conferencing: Optional[Dict] = None


class CalendarManager:
    """
    Unified interface for calendar operations.
    
    Supports both Google Calendar and Microsoft Outlook Calendar.
    Automatically routes operations to the appropriate provider based on user preferences.
    """
    
    def __init__(self, user_id: str, provider: Optional[CalendarProvider] = None):
        """
        Initialize calendar manager for a user.
        
        Args:
            user_id: User identifier
            provider: Preferred calendar provider (auto-detected if None)
        """
        self.user_id = user_id
        self.provider = provider or self._detect_provider()
    
    def _detect_provider(self) -> CalendarProvider:
        """
        Auto-detect which calendar provider the user has connected.
        
        Returns:
            CalendarProvider enum value
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check for existing OAuth tokens
        cur.execute("""
            SELECT provider FROM oauth_tokens
            WHERE user_id = %s AND provider IN ('google_calendar', 'outlook_calendar')
            ORDER BY updated_at DESC
            LIMIT 1
        """, (self.user_id,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            provider_str = row[0]
            if provider_str == 'google_calendar':
                return CalendarProvider.GOOGLE
            elif provider_str == 'outlook_calendar':
                return CalendarProvider.OUTLOOK
        
        # Default to Google if no preference found
        return CalendarProvider.GOOGLE
    
    def set_provider(self, provider: CalendarProvider):
        """Set the calendar provider to use."""
        self.provider = provider
    
    def get_provider(self) -> CalendarProvider:
        """Get the current calendar provider."""
        return self.provider
    
    def start_oauth_flow(self) -> str:
        """
        Start OAuth authentication flow for the selected provider.
        
        Implements FR-CAL-001: Calendar API integration.
        
        Returns:
            Authorization URL to redirect user to
        """
        if self.provider == CalendarProvider.GOOGLE:
            return authenticate_google_calendar(self.user_id)
        elif self.provider == CalendarProvider.OUTLOOK:
            return authenticate_outlook_calendar(self.user_id)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def complete_oauth_flow(self, code: str):
        """
        Complete OAuth authentication flow.
        
        Implements FR-CAL-001: Calendar API integration.
        
        Args:
            code: Authorization code from OAuth callback
        """
        if self.provider == CalendarProvider.GOOGLE:
            complete_google_calendar_oauth(self.user_id, code)
        elif self.provider == CalendarProvider.OUTLOOK:
            complete_outlook_calendar_oauth(self.user_id, code)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def is_authenticated(self) -> bool:
        """
        Check if user is authenticated with their calendar provider.
        
        Returns:
            True if authenticated and token is valid
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        provider_str = 'google_calendar' if self.provider == CalendarProvider.GOOGLE else 'outlook_calendar'
        
        cur.execute("""
            SELECT expires_at FROM oauth_tokens
            WHERE user_id = %s AND provider = %s
        """, (self.user_id, provider_str))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            return False
        
        expires_at = row[0]
        return datetime.utcnow() < expires_at
    
    def check_availability(
        self,
        start: datetime,
        end: datetime,
        duration_minutes: int = 30
    ) -> List[TimeSlot]:
        """
        Check calendar availability and return available time slots.
        
        Implements FR-CAL-002: Real-time availability checking.
        
        Args:
            start: Start of time range to check
            end: End of time range to check
            duration_minutes: Required meeting duration in minutes
            
        Returns:
            List of available TimeSlot objects
        """
        if self.provider == CalendarProvider.GOOGLE:
            slots = check_google_availability(self.user_id, start, end, duration_minutes)
        elif self.provider == CalendarProvider.OUTLOOK:
            slots = check_outlook_availability(self.user_id, start, end, duration_minutes)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        # Convert to unified TimeSlot format
        return [TimeSlot(slot.start, slot.end, slot.duration_minutes) for slot in slots]
    
    def find_next_available_slot(
        self,
        duration_minutes: int = 30,
        days_ahead: int = 7,
        working_hours_only: bool = True,
        earliest_time: int = 9,  # 9 AM
        latest_time: int = 17    # 5 PM
    ) -> Optional[TimeSlot]:
        """
        Find the next available time slot.
        
        Args:
            duration_minutes: Required meeting duration
            days_ahead: How many days in the future to search
            working_hours_only: Only search during working hours
            earliest_time: Earliest hour to consider (24-hour format)
            latest_time: Latest hour to consider (24-hour format)
            
        Returns:
            Next available TimeSlot or None
        """
        now = datetime.utcnow()
        search_end = now + timedelta(days=days_ahead)
        
        if working_hours_only:
            # Search day by day during working hours
            current_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            while current_day < search_end:
                day_start = current_day.replace(hour=earliest_time)
                day_end = current_day.replace(hour=latest_time)
                
                # Skip weekends if working hours only
                if current_day.weekday() < 5:  # Monday = 0, Sunday = 6
                    slots = self.check_availability(
                        max(day_start, now),
                        day_end,
                        duration_minutes
                    )
                    
                    if slots:
                        return slots[0]
                
                current_day += timedelta(days=1)
        else:
            slots = self.check_availability(now, search_end, duration_minutes)
            if slots:
                return slots[0]
        
        return None
    
    def book_meeting(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendee_emails: List[str],
        description: Optional[str] = None,
        location: Optional[str] = None,
        add_video_conferencing: bool = True
    ) -> Optional[str]:
        """
        Book a meeting in the calendar.
        
        Implements FR-CAL-003: Automated meeting booking with attendees.
        
        Args:
            title: Meeting title/subject
            start: Meeting start time
            end: Meeting end time
            attendee_emails: List of attendee email addresses
            description: Optional meeting description
            location: Optional physical location
            add_video_conferencing: Add Google Meet or Teams link
            
        Returns:
            Event ID if successful, None otherwise
        """
        if self.provider == CalendarProvider.GOOGLE:
            event_id = book_google_meeting(
                self.user_id,
                title,
                start,
                end,
                attendee_emails,
                description,
                location,
                add_video_conferencing
            )
        elif self.provider == CalendarProvider.OUTLOOK:
            event_id = book_outlook_meeting(
                self.user_id,
                title,
                start,
                end,
                attendee_emails,
                description,
                location,
                add_video_conferencing
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        return event_id
    
    def get_upcoming_meetings(self, days_ahead: int = 7) -> List[Dict]:
        """
        Get upcoming meetings from the calendar.
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            List of meeting dictionaries
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        provider_str = 'google' if self.provider == CalendarProvider.GOOGLE else 'outlook'
        end_date = datetime.utcnow() + timedelta(days=days_ahead)
        
        cur.execute("""
            SELECT event_id, title, start_time, end_time, attendees
            FROM calendar_events
            WHERE user_id = %s 
            AND provider = %s
            AND start_time >= CURRENT_TIMESTAMP
            AND start_time <= %s
            ORDER BY start_time ASC
        """, (self.user_id, provider_str, end_date))
        
        meetings = []
        for row in cur.fetchall():
            meetings.append({
                'event_id': row[0],
                'title': row[1],
                'start': row[2],
                'end': row[3],
                'attendees': row[4]
            })
        
        cur.close()
        conn.close()
        
        return meetings
    
    def propose_meeting_times(
        self,
        attendee_emails: List[str],
        duration_minutes: int,
        num_options: int = 3,
        days_ahead: int = 7,
        working_hours_only: bool = True
    ) -> List[TimeSlot]:
        """
        Propose multiple meeting time options.
        
        Combines FR-CAL-002 (availability checking) to suggest optimal times.
        
        Args:
            attendee_emails: List of attendee email addresses
            duration_minutes: Required meeting duration
            num_options: Number of time slot options to return
            days_ahead: How many days ahead to search
            working_hours_only: Only suggest during working hours
            
        Returns:
            List of proposed TimeSlot objects
        """
        now = datetime.utcnow()
        search_end = now + timedelta(days=days_ahead)
        
        if working_hours_only:
            earliest_time = 9  # 9 AM
            latest_time = 17   # 5 PM
            
            proposals = []
            current_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            while len(proposals) < num_options and current_day < search_end:
                # Skip weekends
                if current_day.weekday() < 5:
                    day_start = current_day.replace(hour=earliest_time)
                    day_end = current_day.replace(hour=latest_time)
                    
                    slots = self.check_availability(
                        max(day_start, now),
                        day_end,
                        duration_minutes
                    )
                    
                    for slot in slots:
                        if len(proposals) < num_options:
                            proposals.append(slot)
                        else:
                            break
                
                current_day += timedelta(days=1)
            
            return proposals
        else:
            slots = self.check_availability(now, search_end, duration_minutes)
            return slots[:num_options]


# Convenience functions for SDR agent integration

def get_user_calendar_manager(user_id: str) -> CalendarManager:
    """
    Get calendar manager for a user with auto-detected provider.
    
    Args:
        user_id: User identifier
        
    Returns:
        CalendarManager instance
    """
    return CalendarManager(user_id)


def quick_book_meeting(
    user_id: str,
    customer_email: str,
    title: str,
    duration_minutes: int = 30,
    description: Optional[str] = None
) -> Optional[Dict]:
    """
    Quick meeting booking - finds next available slot and books it.
    
    Combines FR-CAL-002 (availability) and FR-CAL-003 (booking).
    
    Args:
        user_id: SDR/sales rep user ID
        customer_email: Customer email to invite
        title: Meeting title
        duration_minutes: Meeting duration
        description: Optional meeting description
        
    Returns:
        Dictionary with event_id, start_time, end_time, or None if booking failed
    """
    manager = CalendarManager(user_id)
    
    if not manager.is_authenticated():
        raise ValueError(f"User {user_id} is not authenticated with any calendar provider")
    
    # Find next available slot
    next_slot = manager.find_next_available_slot(duration_minutes=duration_minutes)
    
    if not next_slot:
        return None
    
    # Book the meeting
    event_id = manager.book_meeting(
        title=title,
        start=next_slot.start,
        end=next_slot.end,
        attendee_emails=[customer_email],
        description=description,
        add_video_conferencing=True
    )
    
    if event_id:
        return {
            'event_id': event_id,
            'start_time': next_slot.start,
            'end_time': next_slot.end,
            'provider': manager.get_provider().value
        }
    
    return None


def check_availability_for_prospect(
    user_id: str,
    duration_minutes: int = 30,
    days_ahead: int = 7
) -> List[TimeSlot]:
    """
    Check availability for scheduling with a prospect.
    
    Implements FR-CAL-002: Real-time availability checking.
    
    Args:
        user_id: SDR/sales rep user ID
        duration_minutes: Required meeting duration
        days_ahead: How many days to check
        
    Returns:
        List of available TimeSlot objects
    """
    manager = CalendarManager(user_id)
    
    if not manager.is_authenticated():
        raise ValueError(f"User {user_id} is not authenticated with any calendar provider")
    
    now = datetime.utcnow()
    end = now + timedelta(days=days_ahead)
    
    return manager.check_availability(now, end, duration_minutes)
