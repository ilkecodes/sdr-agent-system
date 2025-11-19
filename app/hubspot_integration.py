"""HubSpot Integration: OAuth 2.0, contact syncing, and bidirectional CRM updates.

FR-CRM-001: OAuth 2.0 authentication with HubSpot
FR-CRM-003: Fetch contact data based on campaign triggers
FR-CRM-004: Store temporary copy in local database
FR-CRM-005: Generate natural language briefing
FR-CRM-006: Update HubSpot with call logs and outcomes

This module handles:
- OAuth 2.0 authentication with HubSpot
- Contact/Company data fetching
- Contact enrichment and briefing generation
- Call log syncing back to HubSpot
- Campaign-triggered contact imports
"""

from __future__ import annotations

import os
import json
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from app.crm import ProspectManager, InteractionManager
from app.tools import KnowledgeBaseTools

load_dotenv()

# HubSpot API credentials (set in .env)
HUBSPOT_CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID")
HUBSPOT_CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET")
HUBSPOT_REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI", "http://localhost:8000/oauth/hubspot/callback")

DB_URL = os.getenv("DATABASE_URL")
assert DB_URL, "DATABASE_URL is required"

engine = create_engine(DB_URL, pool_pre_ping=True)


class HubSpotOAuth:
    """Handle HubSpot OAuth 2.0 flow."""
    
    AUTHORIZE_URL = "https://app.hubspot.com/oauth/authorize"
    TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
    
    # Scopes needed for SDR operations
    SCOPES = [
        "crm.objects.contacts.read",
        "crm.objects.contacts.write",
        "crm.objects.companies.read",
        "crm.objects.deals.read",
        "crm.schemas.contacts.read",
        "crm.schemas.companies.read",
        "timeline"  # For logging activities
    ]
    
    @staticmethod
    def get_authorization_url(state: Optional[str] = None) -> str:
        """
        Generate OAuth authorization URL.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "client_id": HUBSPOT_CLIENT_ID,
            "redirect_uri": HUBSPOT_REDIRECT_URI,
            "scope": " ".join(HubSpotOAuth.SCOPES),
            "state": state or os.urandom(16).hex()
        }
        return f"{HubSpotOAuth.AUTHORIZE_URL}?{urlencode(params)}"
    
    @staticmethod
    def exchange_code_for_token(code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Token response with access_token, refresh_token, expires_in
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": HUBSPOT_CLIENT_ID,
            "client_secret": HUBSPOT_CLIENT_SECRET,
            "redirect_uri": HUBSPOT_REDIRECT_URI
        }
        
        response = requests.post(HubSpotOAuth.TOKEN_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        # Store token in database
        HubSpotOAuth.store_token(token_data)
        
        return token_data
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
        """
        Refresh expired access token.
        
        Args:
            refresh_token: Refresh token from initial OAuth flow
            
        Returns:
            New token response
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": HUBSPOT_CLIENT_ID,
            "client_secret": HUBSPOT_CLIENT_SECRET
        }
        
        response = requests.post(HubSpotOAuth.TOKEN_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        HubSpotOAuth.store_token(token_data)
        
        return token_data
    
    @staticmethod
    def store_token(token_data: Dict[str, Any]):
        """Store OAuth token in database."""
        sql = text("""
            INSERT INTO oauth_tokens (
                provider, access_token, refresh_token, expires_at, scope, created_at
            ) VALUES (
                'hubspot', :access_token, :refresh_token, 
                NOW() + INTERVAL '1 second' * :expires_in,
                :scope, NOW()
            )
            ON CONFLICT (provider) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token, oauth_tokens.refresh_token),
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
        """)
        
        with engine.begin() as conn:
            conn.execute(sql, {
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in", 1800),
                "scope": " ".join(HubSpotOAuth.SCOPES)
            })
    
    @staticmethod
    def get_token() -> Optional[str]:
        """Get valid access token from database (refresh if expired)."""
        sql = text("""
            SELECT access_token, refresh_token, expires_at 
            FROM oauth_tokens 
            WHERE provider = 'hubspot'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        with engine.connect() as conn:
            result = conn.execute(sql).fetchone()
            
            if not result:
                return None
            
            access_token, refresh_token, expires_at = result
            
            # Check if expired (refresh 5 min before expiry)
            if expires_at and datetime.now() >= (expires_at - timedelta(minutes=5)):
                if refresh_token:
                    # Refresh token
                    new_token = HubSpotOAuth.refresh_access_token(refresh_token)
                    return new_token["access_token"]
                return None
            
            return access_token


class HubSpotClient:
    """Client for HubSpot CRM API operations."""
    
    BASE_URL = "https://api.hubapi.com"
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize HubSpot client.
        
        Args:
            access_token: OAuth access token (fetches from DB if not provided)
        """
        self.access_token = access_token or HubSpotOAuth.get_token()
        if not self.access_token:
            raise ValueError("No valid HubSpot access token found. Please authenticate first.")
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated API request."""
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["Content-Type"] = "application/json"
        
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        
        return response.json() if response.content else {}
    
    # Contact Operations
    
    def get_contact(self, contact_id: str, properties: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get contact by ID.
        
        Args:
            contact_id: HubSpot contact ID
            properties: List of properties to fetch (defaults to common ones)
            
        Returns:
            Contact object with properties
        """
        if properties is None:
            properties = [
                "email", "firstname", "lastname", "company", "jobtitle",
                "phone", "website", "industry", "lifecyclestage",
                "hs_lead_status", "notes_last_contacted", "num_contacted_notes"
            ]
        
        params = {"properties": ",".join(properties)}
        return self._request("GET", f"/crm/v3/objects/contacts/{contact_id}", params=params)
    
    def search_contacts(self, filters: List[Dict[str, Any]], limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search contacts with filters.
        
        Args:
            filters: List of filter objects
            limit: Max results
            
        Returns:
            List of contact objects
        """
        payload = {
            "filterGroups": [{"filters": filters}],
            "limit": limit
        }
        
        result = self._request("POST", "/crm/v3/objects/contacts/search", json=payload)
        return result.get("results", [])
    
    def get_contacts_by_list(self, list_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all contacts in a specific list."""
        # HubSpot uses lists/segments for grouping
        params = {"limit": limit}
        result = self._request("GET", f"/contacts/v1/lists/{list_id}/contacts/all", params=params)
        return result.get("contacts", [])
    
    def update_contact(self, contact_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update contact properties.
        
        Args:
            contact_id: HubSpot contact ID
            properties: Dictionary of properties to update
            
        Returns:
            Updated contact object
        """
        payload = {"properties": properties}
        return self._request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", json=payload)
    
    # Company Operations
    
    def get_company(self, company_id: str) -> Dict[str, Any]:
        """Get company by ID."""
        return self._request("GET", f"/crm/v3/objects/companies/{company_id}")
    
    def get_contact_companies(self, contact_id: str) -> List[Dict[str, Any]]:
        """Get companies associated with a contact."""
        result = self._request("GET", f"/crm/v3/objects/contacts/{contact_id}/associations/companies")
        
        companies = []
        for assoc in result.get("results", []):
            company_id = assoc.get("id")
            if company_id:
                company = self.get_company(company_id)
                companies.append(company)
        
        return companies
    
    # Activity/Engagement Operations
    
    def create_note(self, contact_id: str, note_body: str) -> Dict[str, Any]:
        """
        Create a note on a contact (for call logs).
        
        Args:
            contact_id: HubSpot contact ID
            note_body: Note content (call summary, outcome, etc.)
            
        Returns:
            Created note object
        """
        payload = {
            "properties": {
                "hs_timestamp": datetime.now().isoformat(),
                "hs_note_body": note_body
            }
        }
        
        note = self._request("POST", "/crm/v3/objects/notes", json=payload)
        
        # Associate note with contact
        note_id = note["id"]
        assoc_payload = [{
            "from": {"id": note_id},
            "to": {"id": contact_id},
            "type": "note_to_contact"
        }]
        
        self._request("PUT", f"/crm/v3/associations/notes/contacts/batch/create", json=assoc_payload)
        
        return note
    
    def create_call_activity(
        self, 
        contact_id: str, 
        duration_ms: int,
        outcome: str,
        recording_url: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log a call activity in HubSpot.
        
        Args:
            contact_id: HubSpot contact ID
            duration_ms: Call duration in milliseconds
            outcome: Call outcome (CONNECTED, NO_ANSWER, LEFT_VOICEMAIL, etc.)
            recording_url: Optional recording URL
            notes: Call notes/summary
            
        Returns:
            Created call engagement
        """
        payload = {
            "properties": {
                "hs_timestamp": datetime.now().isoformat(),
                "hs_call_duration": duration_ms,
                "hs_call_status": outcome,
                "hs_call_body": notes or "",
                "hs_call_recording_url": recording_url or ""
            }
        }
        
        call = self._request("POST", "/crm/v3/objects/calls", json=payload)
        
        # Associate with contact
        call_id = call["id"]
        assoc_payload = [{
            "from": {"id": call_id},
            "to": {"id": contact_id},
            "type": "call_to_contact"
        }]
        
        self._request("PUT", "/crm/v3/associations/calls/contacts/batch/create", json=assoc_payload)
        
        return call


class HubSpotSync:
    """Sync HubSpot contacts with local CRM."""
    
    @staticmethod
    def import_contact(contact_id: str) -> int:
        """
        Import a HubSpot contact into local CRM.
        
        Args:
            contact_id: HubSpot contact ID
            
        Returns:
            Local prospect_id
        """
        client = HubSpotClient()
        
        # Fetch contact data
        hs_contact = client.get_contact(contact_id)
        props = hs_contact.get("properties", {})
        
        # Fetch associated companies
        companies = client.get_contact_companies(contact_id)
        company_name = companies[0].get("properties", {}).get("name") if companies else props.get("company")
        
        # Create local prospect
        prospect_id = ProspectManager.create_prospect(
            email=props.get("email"),
            first_name=props.get("firstname"),
            last_name=props.get("lastname"),
            company_name=company_name,
            job_title=props.get("jobtitle"),
            linkedin_url=props.get("linkedin_url"),
            source="hubspot",
            external_id=contact_id
        )
        
        # Store HubSpot metadata
        HubSpotSync._store_sync_metadata(prospect_id, "hubspot", contact_id, hs_contact)
        
        return prospect_id
    
    @staticmethod
    def import_contacts_by_filter(filters: List[Dict[str, Any]], limit: int = 100) -> List[int]:
        """
        Import multiple contacts matching filters.
        
        Args:
            filters: HubSpot search filters
            limit: Max contacts to import
            
        Returns:
            List of local prospect_ids
        """
        client = HubSpotClient()
        contacts = client.search_contacts(filters, limit=limit)
        
        prospect_ids = []
        for contact in contacts:
            contact_id = contact.get("id")
            if contact_id:
                prospect_id = HubSpotSync.import_contact(contact_id)
                prospect_ids.append(prospect_id)
        
        return prospect_ids
    
    @staticmethod
    def sync_call_log(prospect_id: int, interaction_id: int) -> Dict[str, Any]:
        """
        Sync a local interaction back to HubSpot as a call log.
        
        Args:
            prospect_id: Local prospect ID
            interaction_id: Local interaction ID
            
        Returns:
            HubSpot call object
        """
        # Get prospect's HubSpot ID
        external_id = HubSpotSync._get_external_id(prospect_id, "hubspot")
        if not external_id:
            raise ValueError(f"Prospect {prospect_id} not synced with HubSpot")
        
        # Get interaction details
        with engine.connect() as conn:
            sql = text("SELECT * FROM interactions WHERE id = :id")
            result = conn.execute(sql, {"id": interaction_id}).fetchone()
            
            if not result:
                raise ValueError(f"Interaction {interaction_id} not found")
            
            interaction = dict(result._mapping)
        
        # Create call in HubSpot
        client = HubSpotClient()
        
        # Map interaction to HubSpot call
        outcome_map = {
            "sent": "CONNECTED",
            "replied": "CONNECTED",
            "bounced": "NO_ANSWER",
            "failed": "BUSY"
        }
        
        duration_ms = interaction.get("metadata", {}).get("duration_seconds", 0) * 1000
        
        call = client.create_call_activity(
            contact_id=external_id,
            duration_ms=duration_ms,
            outcome=outcome_map.get(interaction.get("status"), "CONNECTED"),
            notes=interaction.get("content", "")
        )
        
        # Update local interaction with HubSpot ID
        with engine.begin() as conn:
            sql = text("""
                UPDATE interactions 
                SET metadata = metadata || :sync_meta::jsonb
                WHERE id = :id
            """)
            conn.execute(sql, {
                "id": interaction_id,
                "sync_meta": json.dumps({"hubspot_call_id": call["id"]})
            })
        
        return call
    
    @staticmethod
    def generate_briefing(prospect_id: int, use_kb: bool = True) -> str:
        """
        Generate natural language briefing for prospect (FR-CRM-005).
        
        Args:
            prospect_id: Local prospect ID
            use_kb: Use knowledge base for context
            
        Returns:
            Natural language briefing text
        """
        # Get prospect data
        prospect = ProspectManager.get_prospect(prospect_id)
        if not prospect:
            return "No prospect found"
        
        # Build briefing
        sections = []
        
        # Basic info
        sections.append(f"**Contact:** {prospect.get('first_name', '')} {prospect.get('last_name', '')}")
        sections.append(f"**Title:** {prospect.get('job_title', 'N/A')}")
        sections.append(f"**Company:** {prospect.get('company_name', 'N/A')}")
        sections.append(f"**Email:** {prospect.get('email')}")
        sections.append("")
        
        # Interaction history
        interactions = InteractionManager.get_interactions(prospect_id, limit=5)
        if interactions:
            sections.append("**Recent Interactions:**")
            for i in interactions[:3]:
                sections.append(f"- {i['created_at']}: {i['type']} via {i['channel']} ({i['status']})")
            sections.append("")
        
        # Knowledge base context
        if use_kb and prospect.get('company_name'):
            kb_context = KnowledgeBaseTools.search_knowledge(
                query=f"{prospect.get('company_name')} {prospect.get('job_title', '')}",
                top_k=3
            )
            
            if kb_context and not kb_context[0].get("error"):
                sections.append("**Knowledge Base Context:**")
                for chunk in kb_context[:2]:
                    preview = chunk.get('content', '')[:200]
                    sections.append(f"- {preview}...")
                sections.append("")
        
        # Notes
        if prospect.get('notes'):
            sections.append(f"**Notes:** {prospect['notes']}")
            sections.append("")
        
        return "\n".join(sections)
    
    @staticmethod
    def _store_sync_metadata(prospect_id: int, provider: str, external_id: str, raw_data: Dict[str, Any]):
        """Store CRM sync metadata."""
        sql = text("""
            INSERT INTO crm_sync_metadata (
                prospect_id, provider, external_id, raw_data, synced_at
            ) VALUES (
                :prospect_id, :provider, :external_id, :raw_data, NOW()
            )
            ON CONFLICT (prospect_id, provider) DO UPDATE SET
                external_id = EXCLUDED.external_id,
                raw_data = EXCLUDED.raw_data,
                synced_at = NOW()
        """)
        
        with engine.begin() as conn:
            conn.execute(sql, {
                "prospect_id": prospect_id,
                "provider": provider,
                "external_id": external_id,
                "raw_data": json.dumps(raw_data)
            })
    
    @staticmethod
    def _get_external_id(prospect_id: int, provider: str) -> Optional[str]:
        """Get external CRM ID for prospect."""
        sql = text("""
            SELECT external_id FROM crm_sync_metadata
            WHERE prospect_id = :prospect_id AND provider = :provider
        """)
        
        with engine.connect() as conn:
            result = conn.execute(sql, {"prospect_id": prospect_id, "provider": provider}).fetchone()
            return result[0] if result else None


# Convenience functions
def authenticate_hubspot() -> str:
    """Get OAuth authorization URL for HubSpot."""
    return HubSpotOAuth.get_authorization_url()


def complete_hubspot_oauth(code: str) -> Dict[str, Any]:
    """Complete OAuth flow with authorization code."""
    return HubSpotOAuth.exchange_code_for_token(code)


def import_hubspot_contact(contact_id: str) -> int:
    """Import single HubSpot contact."""
    return HubSpotSync.import_contact(contact_id)


def sync_interaction_to_hubspot(prospect_id: int, interaction_id: int) -> Dict[str, Any]:
    """Sync interaction to HubSpot."""
    return HubSpotSync.sync_call_log(prospect_id, interaction_id)


def generate_prospect_briefing(prospect_id: int) -> str:
    """Generate pre-call briefing."""
    return HubSpotSync.generate_briefing(prospect_id)
