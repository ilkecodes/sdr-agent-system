"""
Calendar Integration Workflow Examples

Demonstrates complete workflows for Google Calendar and Outlook Calendar integrations.
Shows OAuth setup, availability checking, meeting booking, and SDR agent integration.

Run examples:
    python examples/calendar_workflow.py
"""

import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.calendar_manager import (
    CalendarManager,
    CalendarProvider,
    quick_book_meeting,
    check_availability_for_prospect
)
from app.google_calendar_integration import authenticate_google_calendar, complete_google_calendar_oauth
from app.outlook_calendar_integration import authenticate_outlook_calendar, complete_outlook_calendar_oauth


def example_google_calendar_setup():
    """
    Example: Set up Google Calendar integration for a user.
    
    Implements FR-CAL-001: Google Calendar API integration
    """
    print("=" * 60)
    print("Google Calendar Setup Example")
    print("=" * 60)
    
    user_id = "sales_rep_001"
    
    # Step 1: Start OAuth flow
    print(f"\n1. Starting OAuth flow for user: {user_id}")
    auth_url = authenticate_google_calendar(user_id)
    print(f"   Authorization URL: {auth_url}")
    print("   -> User should visit this URL and authorize")
    
    # Step 2: After user authorizes (simulated)
    print("\n2. After user authorizes, exchange code for token")
    print("   authorization_code = '4/0AfJohXm...'  # From callback")
    print("   complete_google_calendar_oauth(user_id, authorization_code)")
    print("   ✓ OAuth tokens stored in database")
    
    print("\n✅ Google Calendar setup complete!")
    print(f"   User {user_id} can now use calendar features\n")


def example_outlook_calendar_setup():
    """
    Example: Set up Microsoft Outlook Calendar integration for a user.
    
    Implements FR-CAL-001: Outlook Calendar API integration
    """
    print("=" * 60)
    print("Microsoft Outlook Calendar Setup Example")
    print("=" * 60)
    
    user_id = "sales_rep_002"
    
    # Step 1: Start OAuth flow
    print(f"\n1. Starting OAuth flow for user: {user_id}")
    auth_url = authenticate_outlook_calendar(user_id)
    print(f"   Authorization URL: {auth_url}")
    print("   -> User should visit this URL and authorize")
    
    # Step 2: After user authorizes (simulated)
    print("\n2. After user authorizes, exchange code for token")
    print("   authorization_code = 'M.C507_BAY...'  # From callback")
    print("   complete_outlook_calendar_oauth(user_id, authorization_code)")
    print("   ✓ OAuth tokens stored in database")
    
    print("\n✅ Outlook Calendar setup complete!")
    print(f"   User {user_id} can now use calendar features\n")


def example_check_availability():
    """
    Example: Check calendar availability for the next 7 days.
    
    Implements FR-CAL-002: Real-time availability checking
    """
    print("=" * 60)
    print("Check Availability Example")
    print("=" * 60)
    
    user_id = "sales_rep_001"
    
    print(f"\nChecking availability for user: {user_id}")
    
    # Create calendar manager (auto-detects provider)
    manager = CalendarManager(user_id)
    print(f"Provider: {manager.get_provider().value}")
    
    # Check availability for next 7 days
    start = datetime.utcnow()
    end = start + timedelta(days=7)
    
    print(f"\nSearching for 30-minute slots between:")
    print(f"  Start: {start.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  End:   {end.strftime('%Y-%m-%d %H:%M UTC')}")
    
    try:
        slots = manager.check_availability(start, end, duration_minutes=30)
        
        print(f"\n✅ Found {len(slots)} available 30-minute slots:")
        
        # Show first 10 slots
        for i, slot in enumerate(slots[:10], 1):
            print(f"   {i}. {slot.start.strftime('%A, %B %d at %I:%M %p')} - {slot.end.strftime('%I:%M %p')}")
        
        if len(slots) > 10:
            print(f"   ... and {len(slots) - 10} more slots")
    
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("   User may need to authenticate first")
    
    print()


def example_find_next_available():
    """
    Example: Find the next available time slot.
    
    Implements FR-CAL-002: Real-time availability checking
    """
    print("=" * 60)
    print("Find Next Available Slot Example")
    print("=" * 60)
    
    user_id = "sales_rep_001"
    
    print(f"\nFinding next available slot for user: {user_id}")
    
    manager = CalendarManager(user_id)
    
    try:
        # Find next available 30-minute slot during working hours
        next_slot = manager.find_next_available_slot(
            duration_minutes=30,
            days_ahead=7,
            working_hours_only=True,
            earliest_time=9,  # 9 AM
            latest_time=17    # 5 PM
        )
        
        if next_slot:
            print(f"\n✅ Next available slot:")
            print(f"   Start: {next_slot.start.strftime('%A, %B %d, %Y at %I:%M %p')}")
            print(f"   End:   {next_slot.end.strftime('%I:%M %p')}")
            print(f"   Duration: {next_slot.duration_minutes} minutes")
        else:
            print("\n❌ No available slots found in the next 7 days")
    
    except ValueError as e:
        print(f"\n❌ Error: {e}")
    
    print()


def example_book_meeting():
    """
    Example: Book a meeting with a prospect.
    
    Implements FR-CAL-003: Automated meeting booking with attendees
    """
    print("=" * 60)
    print("Book Meeting Example")
    print("=" * 60)
    
    user_id = "sales_rep_001"
    prospect_email = "john.doe@acmecorp.com"
    
    print(f"\nBooking meeting for user: {user_id}")
    print(f"Inviting prospect: {prospect_email}")
    
    manager = CalendarManager(user_id)
    
    try:
        # Find next available slot
        next_slot = manager.find_next_available_slot(duration_minutes=30)
        
        if not next_slot:
            print("\n❌ No available slots found")
            return
        
        print(f"\nFound available slot: {next_slot.start.strftime('%A, %B %d at %I:%M %p')}")
        
        # Book the meeting
        print("\nBooking meeting...")
        event_id = manager.book_meeting(
            title="Product Demo - Acme Corp",
            start=next_slot.start,
            end=next_slot.end,
            attendee_emails=[prospect_email],
            description="Personalized demo of our enterprise platform features",
            location="Virtual",
            add_video_conferencing=True  # Adds Google Meet or Teams link
        )
        
        if event_id:
            print(f"\n✅ Meeting booked successfully!")
            print(f"   Event ID: {event_id}")
            print(f"   Provider: {manager.get_provider().value}")
            print(f"   Time: {next_slot.start.strftime('%A, %B %d, %Y at %I:%M %p')}")
            print(f"   Attendees: {prospect_email}")
            print(f"   Video: {'Google Meet' if manager.get_provider() == CalendarProvider.GOOGLE else 'Microsoft Teams'}")
            print("\n   📧 Calendar invitation sent to attendee")
        else:
            print("\n❌ Failed to book meeting")
    
    except ValueError as e:
        print(f"\n❌ Error: {e}")
    
    print()


def example_quick_book():
    """
    Example: Quick meeting booking (finds and books in one step).
    
    Combines FR-CAL-002 and FR-CAL-003
    """
    print("=" * 60)
    print("Quick Book Meeting Example")
    print("=" * 60)
    
    user_id = "sales_rep_001"
    customer_email = "jane.smith@techstart.io"
    
    print(f"\nQuick booking for user: {user_id}")
    print(f"Customer: {customer_email}")
    
    try:
        result = quick_book_meeting(
            user_id=user_id,
            customer_email=customer_email,
            title="Discovery Call - TechStart",
            duration_minutes=30,
            description="Initial discovery call to understand requirements"
        )
        
        if result:
            print(f"\n✅ Meeting booked successfully!")
            print(f"   Event ID: {result['event_id']}")
            print(f"   Provider: {result['provider']}")
            print(f"   Start: {result['start_time'].strftime('%A, %B %d, %Y at %I:%M %p')}")
            print(f"   End: {result['end_time'].strftime('%I:%M %p')}")
            print("\n   This function automatically:")
            print("   1. Found the next available time slot")
            print("   2. Booked the meeting")
            print("   3. Sent calendar invitation to customer")
            print("   4. Added video conferencing link")
        else:
            print("\n❌ No available slots found in the next 7 days")
    
    except ValueError as e:
        print(f"\n❌ Error: {e}")
    
    print()


def example_propose_meeting_times():
    """
    Example: Propose multiple meeting time options to a prospect.
    
    Implements FR-CAL-002: Real-time availability checking
    """
    print("=" * 60)
    print("Propose Meeting Times Example")
    print("=" * 60)
    
    user_id = "sales_rep_001"
    prospect_email = "ceo@bigclient.com"
    
    print(f"\nProposing meeting times for user: {user_id}")
    print(f"Prospect: {prospect_email}")
    
    manager = CalendarManager(user_id)
    
    try:
        # Propose 3 meeting time options
        proposals = manager.propose_meeting_times(
            attendee_emails=[prospect_email],
            duration_minutes=45,
            num_options=3,
            days_ahead=7,
            working_hours_only=True
        )
        
        if proposals:
            print(f"\n✅ Proposed meeting times (45 minutes each):\n")
            
            for i, slot in enumerate(proposals, 1):
                print(f"   Option {i}: {slot.start.strftime('%A, %B %d, %Y')}")
                print(f"              {slot.start.strftime('%I:%M %p')} - {slot.end.strftime('%I:%M %p')} UTC")
                print()
            
            print("   Send these options to the prospect via email")
            print("   Then use book_meeting() when they confirm")
        else:
            print("\n❌ No available slots found")
    
    except ValueError as e:
        print(f"\n❌ Error: {e}")
    
    print()


def example_sdr_agent_integration():
    """
    Example: How the SDR agent uses calendar integration.
    
    Implements FR-CAL-002 and FR-CAL-003 in SDR workflow
    """
    print("=" * 60)
    print("SDR Agent Calendar Integration Example")
    print("=" * 60)
    
    print("\nScenario: SDR agent qualifies a prospect and wants to book a demo\n")
    
    # Simulated SDR agent workflow
    sdr_user_id = "sales_rep_001"
    prospect = {
        "name": "Alex Johnson",
        "email": "alex@innovate.tech",
        "company": "Innovate Tech",
        "role": "VP of Engineering"
    }
    
    print(f"Prospect: {prospect['name']} ({prospect['role']} at {prospect['company']})")
    print(f"Email: {prospect['email']}")
    
    print("\n--- SDR Agent Workflow ---\n")
    
    # Step 1: Check availability
    print("1. Agent checks SDR's calendar availability...")
    
    try:
        manager = CalendarManager(sdr_user_id)
        
        next_slot = manager.find_next_available_slot(
            duration_minutes=30,
            days_ahead=5,
            working_hours_only=True
        )
        
        if next_slot:
            print(f"   ✓ Found available slot: {next_slot.start.strftime('%A, %B %d at %I:%M %p')}")
        else:
            print("   ✗ No slots available in next 5 days")
            return
        
        # Step 2: Generate personalized message
        print("\n2. Agent generates personalized meeting invite...")
        
        meeting_description = f"""Hi {prospect['name']},

Thank you for your interest in our platform. Based on our conversation, I'd like to show you how we can help {prospect['company']} achieve [specific goals].

This 30-minute demo will cover:
- Key features relevant to your use case
- Live Q&A
- Next steps discussion

Looking forward to connecting!"""
        
        print("   ✓ Personalized description generated")
        
        # Step 3: Book the meeting
        print("\n3. Agent books the meeting...")
        
        event_id = manager.book_meeting(
            title=f"Product Demo - {prospect['company']}",
            start=next_slot.start,
            end=next_slot.end,
            attendee_emails=[prospect['email']],
            description=meeting_description,
            add_video_conferencing=True
        )
        
        if event_id:
            print(f"   ✓ Meeting booked (Event ID: {event_id})")
            print(f"   ✓ Calendar invitation sent to {prospect['email']}")
            print(f"   ✓ Video conferencing link added")
        
        # Step 4: Log in CRM
        print("\n4. Agent logs meeting in CRM...")
        print("   ✓ Interaction recorded in prospects table")
        print(f"   ✓ Meeting scheduled for: {next_slot.start.strftime('%Y-%m-%d %H:%M UTC')}")
        
        # Step 5: Send confirmation email
        print("\n5. Agent sends confirmation email to prospect...")
        print(f"   To: {prospect['email']}")
        print(f"   Subject: Demo Scheduled - {next_slot.start.strftime('%A, %B %d')}")
        print("   ✓ Email sent with calendar invite and preparation tips")
        
        print("\n" + "=" * 60)
        print("✅ Complete SDR workflow executed successfully!")
        print("=" * 60)
        print("\nWhat happened:")
        print("  1. Checked calendar availability (FR-CAL-002)")
        print("  2. Found optimal meeting time")
        print("  3. Booked meeting with attendee (FR-CAL-003)")
        print("  4. Sent automated calendar invitation")
        print("  5. Logged all interactions")
        
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("   SDR needs to authenticate calendar first")
    
    print()


def example_multi_provider_support():
    """
    Example: Working with both Google and Outlook calendars.
    
    Demonstrates FR-CAL-001: Multi-provider support
    """
    print("=" * 60)
    print("Multi-Provider Support Example")
    print("=" * 60)
    
    print("\nThe system supports both Google Calendar and Outlook Calendar")
    print("Users can choose their preferred provider\n")
    
    # Example with explicit provider selection
    user_id = "sales_rep_003"
    
    print(f"User: {user_id}")
    print("\nOption 1: Auto-detect provider (recommended)")
    print("  manager = CalendarManager(user_id)")
    print("  # Automatically uses the last connected calendar")
    
    print("\nOption 2: Explicitly choose Google Calendar")
    print("  manager = CalendarManager(user_id, provider=CalendarProvider.GOOGLE)")
    
    print("\nOption 3: Explicitly choose Outlook Calendar")
    print("  manager = CalendarManager(user_id, provider=CalendarProvider.OUTLOOK)")
    
    print("\nAll methods work the same regardless of provider:")
    print("  - check_availability()")
    print("  - book_meeting()")
    print("  - find_next_available_slot()")
    print("  - propose_meeting_times()")
    
    print("\n✅ Provider abstraction allows seamless switching!")
    print()


def main():
    """Run all calendar integration examples."""
    
    print("\n" + "=" * 60)
    print("CALENDAR INTEGRATION WORKFLOW EXAMPLES")
    print("=" * 60)
    print("\nThese examples demonstrate:")
    print("  • FR-CAL-001: Google & Outlook Calendar API integration")
    print("  • FR-CAL-002: Real-time availability checking")
    print("  • FR-CAL-003: Automated meeting booking with attendees")
    print("\n" + "=" * 60 + "\n")
    
    input("Press Enter to continue...")
    
    # Setup examples
    example_google_calendar_setup()
    input("Press Enter to continue...")
    
    example_outlook_calendar_setup()
    input("Press Enter to continue...")
    
    # Availability checking examples
    example_check_availability()
    input("Press Enter to continue...")
    
    example_find_next_available()
    input("Press Enter to continue...")
    
    # Booking examples
    example_book_meeting()
    input("Press Enter to continue...")
    
    example_quick_book()
    input("Press Enter to continue...")
    
    example_propose_meeting_times()
    input("Press Enter to continue...")
    
    # Advanced examples
    example_sdr_agent_integration()
    input("Press Enter to continue...")
    
    example_multi_provider_support()
    
    print("\n" + "=" * 60)
    print("ALL EXAMPLES COMPLETED")
    print("=" * 60)
    print("\nFor more information, see:")
    print("  • docs/CALENDAR_INTEGRATIONS.md - Complete documentation")
    print("  • app/calendar_manager.py - Unified calendar interface")
    print("  • app/google_calendar_integration.py - Google Calendar client")
    print("  • app/outlook_calendar_integration.py - Outlook Calendar client")
    print()


if __name__ == "__main__":
    main()
