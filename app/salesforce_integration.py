"""Salesforce Integration: OAuth 2.0, contact/lead syncing, and activity logging.

FR-CRM-002: OAuth 2.0 authentication with Salesforce
FR-CRM-003: Fetch contact/lead data based on campaign triggers  
FR-CRM-004: Store temporary copy in local database
FR-CRM-005: Generate natural language briefing
FR-CRM-006: Update Salesforce with call logs and outcomes

This module handles:
- OAuth 2.0 authentication with Salesforce
- Contact/Lead/Account data fetching
- Contact enrichment and briefing generation
- Task/Activity logging back to Salesforce
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

# Salesforce API credentials (set in .env)
SALESFORCE_CLIENT_ID = os.getenv("SALESFORCE_CLIENT_ID")
SALESFORCE_CLIENT_SECRET = os.getenv("SALESFORCE_CLIENT_SECRET")
SALESFORCE_REDIRECT_URI = os.getenv("SALESFORCE_REDIRECT_URI", "http://localhost:8000/oauth/salesforce/callback")
SALESFORCE_INSTANCE_URL = os.getenv("SALESFORCE_INSTANCE_URL", "https://login.salesforce.com")  # or test.salesforce.com for sandbox

DB_URL = os.getenv("DATABASE_URL")
assert DB_URL, "DATABASE_URL is required"

engine = create_engine(DB_URL, pool_pre_ping=True)


class SalesforceOAuth:
    """Handle Salesforce OAuth 2.0 flow."""
    
    AUTHORIZE_URL = f"{SALESFORCE_INSTANCE_URL}/services/oauth2/authorize"
    TOKEN_URL = f"{SALESFORCE_INSTANCE_URL}/services/oauth2/token"
    
    # Scopes needed for SDR operations
    SCOPES = [
        "api",  # Access to Salesforce APIs
        "refresh_token",  # Ability to refresh token
        "offline_access"  # Maintain access
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
            "response_type": "code",
            "client_id": SALESFORCE_CLIENT_ID,
            "redirect_uri": SALESFORCE_REDIRECT_URI,
            "scope": " ".join(SalesforceOAuth.SCOPES),
            "state": state or os.urandom(16).hex()
        }
        return f"{SalesforceOAuth.AUTHORIZE_URL}?{urlencode(params)}"
    
    @staticmethod
    def exchange_code_for_token(code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Token response with access_token, refresh_token, instance_url
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": SALESFORCE_CLIENT_ID,
            "client_secret": SALESFORCE_CLIENT_SECRET,
            "redirect_uri": SALESFORCE_REDIRECT_URI
        }
        
        response = requests.post(SalesforceOAuth.TOKEN_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        # Store token in database
        SalesforceOAuth.store_token(token_data)
        
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
            "client_id": SALESFORCE_CLIENT_ID,
            "client_secret": SALESFORCE_CLIENT_SECRET
        }
        
        response = requests.post(SalesforceOAuth.TOKEN_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        SalesforceOAuth.store_token(token_data)
        
        return token_data
    
    @staticmethod
    def store_token(token_data: Dict[str, Any]):
        """Store OAuth token in database."""
        # Salesforce tokens don't have expiry in response, typically valid for 2 hours
        expires_in = token_data.get("expires_in", 7200)
        
        sql = text("""
            INSERT INTO oauth_tokens (
                provider, access_token, refresh_token, expires_at, scope, 
                metadata, created_at
            ) VALUES (
                'salesforce', :access_token, :refresh_token, 
                NOW() + INTERVAL '1 second' * :expires_in,
                :scope, :metadata, NOW()
            )
            ON CONFLICT (provider) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token, oauth_tokens.refresh_token),
                expires_at = EXCLUDED.expires_at,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
        """)
        
        with engine.begin() as conn:
            conn.execute(sql, {
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": expires_in,
                "scope": " ".join(SalesforceOAuth.SCOPES),
                "metadata": json.dumps({
                    "instance_url": token_data.get("instance_url"),
                    "id": token_data.get("id"),
                    "issued_at": token_data.get("issued_at")
                })
            })
    
    @staticmethod
    def get_token() -> Optional[tuple[str, str]]:
        """Get valid access token and instance URL from database (refresh if expired)."""
        sql = text("""
            SELECT access_token, refresh_token, expires_at, metadata
            FROM oauth_tokens 
            WHERE provider = 'salesforce'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        with engine.connect() as conn:
            result = conn.execute(sql).fetchone()
            
            if not result:
                return None
            
            access_token, refresh_token, expires_at, metadata = result
            instance_url = json.loads(metadata or "{}").get("instance_url", SALESFORCE_INSTANCE_URL)
            
            # Check if expired (refresh 5 min before expiry)
            if expires_at and datetime.now() >= (expires_at - timedelta(minutes=5)):
                if refresh_token:
                    # Refresh token
                    new_token = SalesforceOAuth.refresh_access_token(refresh_token)
                    return new_token["access_token"], new_token.get("instance_url", instance_url)
                return None
            
            return access_token, instance_url


class SalesforceClient:
    """Client for Salesforce REST API operations."""
    
    API_VERSION = "v59.0"  # Update as needed
    
    def __init__(self, access_token: Optional[str] = None, instance_url: Optional[str] = None):
        """
        Initialize Salesforce client.
        
        Args:
            access_token: OAuth access token (fetches from DB if not provided)
            instance_url: Salesforce instance URL
        """
        token_data = SalesforceOAuth.get_token()
        if not token_data:
            raise ValueError("No valid Salesforce access token found. Please authenticate first.")
        
        self.access_token = access_token or token_data[0]
        self.instance_url = instance_url or token_data[1]
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated API request."""
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["Content-Type"] = "application/json"
        
        # Endpoint should start with /services/data/vXX.X/ or be a relative path
        if not endpoint.startswith("/services"):
            endpoint = f"/services/data/{self.API_VERSION}/{endpoint.lstrip('/')}"
        
        url = f"{self.instance_url}{endpoint}"
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        
        return response.json() if response.content else {}
    
    # Lead Operations
    
    def get_lead(self, lead_id: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get lead by ID.
        
        Args:
            lead_id: Salesforce lead ID
            fields: List of fields to fetch
            
        Returns:
            Lead object
        """
        if fields:
            query = f"SELECT {','.join(fields)} FROM Lead WHERE Id = '{lead_id}'"
            result = self.query(query)
            return result.get("records", [{}])[0]
        else:
            return self._request("GET", f"sobjects/Lead/{lead_id}")
    
    def query_leads(self, soql: str) -> List[Dict[str, Any]]:
        """
        Query leads using SOQL.
        
        Args:
            soql: SOQL query string
            
        Returns:
            List of lead records
        """
        result = self.query(soql)
        return result.get("records", [])
    
    def update_lead(self, lead_id: str, fields: Dict[str, Any]) -> bool:
        """
        Update lead fields.
        
        Args:
            lead_id: Salesforce lead ID
            fields: Dictionary of fields to update
            
        Returns:
            Success boolean
        """
        self._request("PATCH", f"sobjects/Lead/{lead_id}", json=fields)
        return True
    
    # Contact Operations
    
    def get_contact(self, contact_id: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get contact by ID."""
        if fields:
            query = f"SELECT {','.join(fields)} FROM Contact WHERE Id = '{contact_id}'"
            result = self.query(query)
            return result.get("records", [{}])[0]
        else:
            return self._request("GET", f"sobjects/Contact/{contact_id}")
    
    def query_contacts(self, soql: str) -> List[Dict[str, Any]]:
        """Query contacts using SOQL."""
        result = self.query(soql)
        return result.get("records", [])
    
    def update_contact(self, contact_id: str, fields: Dict[str, Any]) -> bool:
        """Update contact fields."""
        self._request("PATCH", f"sobjects/Contact/{contact_id}", json=fields)
        return True
    
    # Account Operations
    
    def get_account(self, account_id: str) -> Dict[str, Any]:
        """Get account (company) by ID."""
        return self._request("GET", f"sobjects/Account/{account_id}")
    
    # Task/Activity Operations
    
    def create_task(
        self,
        who_id: str,  # Contact or Lead ID
        subject: str,
        description: Optional[str] = None,
        status: str = "Completed",
        priority: str = "Normal",
        task_subtype: str = "Call"
    ) -> Dict[str, Any]:
        """
        Create a task (for logging calls/activities).
        
        Args:
            who_id: Contact or Lead ID
            subject: Task subject
            description: Task description/notes
            status: Task status (Completed, In Progress, etc.)
            priority: Priority level
            task_subtype: Type of task (Call, Email, etc.)
            
        Returns:
            Created task object
        """
        task_data = {
            "WhoId": who_id,
            "Subject": subject,
            "Description": description or "",
            "Status": status,
            "Priority": priority,
            "TaskSubtype": task_subtype,
            "ActivityDate": datetime.now().date().isoformat()
        }
        
        result = self._request("POST", "sobjects/Task", json=task_data)
        return result
    
    def create_call_log(
        self,
        who_id: str,
        call_type: str,
        duration_minutes: int,
        outcome: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log a call in Salesforce.
        
        Args:
            who_id: Contact or Lead ID
            call_type: Inbound or Outbound
            duration_minutes: Call duration
            outcome: Call outcome
            notes: Call notes
            
        Returns:
            Created task
        """
        subject = f"{call_type} Call - {outcome}"
        description = f"Duration: {duration_minutes} minutes\nOutcome: {outcome}\n\n{notes or ''}"
        
        return self.create_task(
            who_id=who_id,
            subject=subject,
            description=description,
            status="Completed",
            task_subtype="Call"
        )
    
    # Generic Query
    
    def query(self, soql: str) -> Dict[str, Any]:
        """
        Execute SOQL query.
        
        Args:
            soql: SOQL query string
            
        Returns:
            Query results
        """
        params = {"q": soql}
        return self._request("GET", "query", params=params)


class SalesforceSync:
    """Sync Salesforce contacts/leads with local CRM."""
    
    @staticmethod
    def import_lead(lead_id: str) -> int:
        """
        Import a Salesforce lead into local CRM.
        
        Args:
            lead_id: Salesforce lead ID
            
        Returns:
            Local prospect_id
        """
        client = SalesforceClient()
        
        # Fetch lead data
        fields = ["Email", "FirstName", "LastName", "Company", "Title", "Phone", "Website", "Industry", "Status"]
        sf_lead = client.get_lead(lead_id, fields=fields)
        
        # Create local prospect
        prospect_id = ProspectManager.create_prospect(
            email=sf_lead.get("Email"),
            first_name=sf_lead.get("FirstName"),
            last_name=sf_lead.get("LastName"),
            company_name=sf_lead.get("Company"),
            job_title=sf_lead.get("Title"),
            source="salesforce_lead",
            external_id=lead_id
        )
        
        # Store Salesforce metadata
        SalesforceSync._store_sync_metadata(prospect_id, "salesforce", lead_id, sf_lead)
        
        return prospect_id
    
    @staticmethod
    def import_contact(contact_id: str) -> int:
        """
        Import a Salesforce contact into local CRM.
        
        Args:
            contact_id: Salesforce contact ID
            
        Returns:
            Local prospect_id
        """
        client = SalesforceClient()
        
        # Fetch contact data
        fields = ["Email", "FirstName", "LastName", "Title", "Phone", "AccountId"]
        sf_contact = client.get_contact(contact_id, fields=fields)
        
        # Fetch account (company) if available
        company_name = None
        if sf_contact.get("AccountId"):
            account = client.get_account(sf_contact["AccountId"])
            company_name = account.get("Name")
        
        # Create local prospect
        prospect_id = ProspectManager.create_prospect(
            email=sf_contact.get("Email"),
            first_name=sf_contact.get("FirstName"),
            last_name=sf_contact.get("LastName"),
            company_name=company_name,
            job_title=sf_contact.get("Title"),
            source="salesforce_contact",
            external_id=contact_id
        )
        
        # Store Salesforce metadata
        SalesforceSync._store_sync_metadata(prospect_id, "salesforce", contact_id, sf_contact)
        
        return prospect_id
    
    @staticmethod
    def import_by_campaign(campaign_id: str, limit: int = 100) -> List[int]:
        """
        Import contacts/leads from a Salesforce campaign.
        
        Args:
            campaign_id: Salesforce campaign ID
            limit: Max records to import
            
        Returns:
            List of local prospect_ids
        """
        client = SalesforceClient()
        
        # Query campaign members
        soql = f"""
            SELECT ContactId, LeadId 
            FROM CampaignMember 
            WHERE CampaignId = '{campaign_id}' 
            LIMIT {limit}
        """
        
        members = client.query(soql).get("records", [])
        
        prospect_ids = []
        for member in members:
            # Import contact or lead
            if member.get("ContactId"):
                prospect_id = SalesforceSync.import_contact(member["ContactId"])
                prospect_ids.append(prospect_id)
            elif member.get("LeadId"):
                prospect_id = SalesforceSync.import_lead(member["LeadId"])
                prospect_ids.append(prospect_id)
        
        return prospect_ids
    
    @staticmethod
    def sync_call_log(prospect_id: int, interaction_id: int) -> Dict[str, Any]:
        """
        Sync a local interaction back to Salesforce as a task/call log.
        
        Args:
            prospect_id: Local prospect ID
            interaction_id: Local interaction ID
            
        Returns:
            Salesforce task object
        """
        # Get prospect's Salesforce ID
        external_id = SalesforceSync._get_external_id(prospect_id, "salesforce")
        if not external_id:
            raise ValueError(f"Prospect {prospect_id} not synced with Salesforce")
        
        # Get interaction details
        with engine.connect() as conn:
            sql = text("SELECT * FROM interactions WHERE id = :id")
            result = conn.execute(sql, {"id": interaction_id}).fetchone()
            
            if not result:
                raise ValueError(f"Interaction {interaction_id} not found")
            
            interaction = dict(result._mapping)
        
        # Create task in Salesforce
        client = SalesforceClient()
        
        # Map interaction to Salesforce call
        call_type = "Outbound" if interaction.get("direction") == "outbound" else "Inbound"
        duration_minutes = interaction.get("metadata", {}).get("duration_seconds", 0) // 60
        
        outcome_map = {
            "sent": "Connected",
            "replied": "Connected - Follow Up",
            "bounced": "No Answer",
            "failed": "Busy"
        }
        
        task = client.create_call_log(
            who_id=external_id,
            call_type=call_type,
            duration_minutes=duration_minutes,
            outcome=outcome_map.get(interaction.get("status"), "Connected"),
            notes=interaction.get("content", "")
        )
        
        # Update local interaction with Salesforce task ID
        with engine.begin() as conn:
            sql = text("""
                UPDATE interactions 
                SET metadata = metadata || :sync_meta::jsonb
                WHERE id = :id
            """)
            conn.execute(sql, {
                "id": interaction_id,
                "sync_meta": json.dumps({"salesforce_task_id": task["id"]})
            })
        
        return task
    
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
        sections.append(f"**Source:** Salesforce ({prospect.get('source', 'N/A')})")
        sections.append("")
        
        # Salesforce-specific data
        metadata = SalesforceSync._get_sync_metadata(prospect_id, "salesforce")
        if metadata:
            sf_data = json.loads(metadata.get("raw_data", "{}"))
            if sf_data.get("Status"):
                sections.append(f"**Lead Status:** {sf_data['Status']}")
            if sf_data.get("Industry"):
                sections.append(f"**Industry:** {sf_data['Industry']}")
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
    
    @staticmethod
    def _get_sync_metadata(prospect_id: int, provider: str) -> Optional[Dict[str, Any]]:
        """Get full sync metadata for prospect."""
        sql = text("""
            SELECT * FROM crm_sync_metadata
            WHERE prospect_id = :prospect_id AND provider = :provider
        """)
        
        with engine.connect() as conn:
            result = conn.execute(sql, {"prospect_id": prospect_id, "provider": provider}).fetchone()
            return dict(result._mapping) if result else None


# Convenience functions
def authenticate_salesforce() -> str:
    """Get OAuth authorization URL for Salesforce."""
    return SalesforceOAuth.get_authorization_url()


def complete_salesforce_oauth(code: str) -> Dict[str, Any]:
    """Complete OAuth flow with authorization code."""
    return SalesforceOAuth.exchange_code_for_token(code)


def import_salesforce_lead(lead_id: str) -> int:
    """Import single Salesforce lead."""
    return SalesforceSync.import_lead(lead_id)


def import_salesforce_contact(contact_id: str) -> int:
    """Import single Salesforce contact."""
    return SalesforceSync.import_contact(contact_id)


def import_campaign_members(campaign_id: str, limit: int = 100) -> List[int]:
    """Import all members from a Salesforce campaign."""
    return SalesforceSync.import_by_campaign(campaign_id, limit=limit)


def sync_interaction_to_salesforce(prospect_id: int, interaction_id: int) -> Dict[str, Any]:
    """Sync interaction to Salesforce."""
    return SalesforceSync.sync_call_log(prospect_id, interaction_id)


def generate_prospect_briefing(prospect_id: int) -> str:
    """Generate pre-call briefing."""
    return SalesforceSync.generate_briefing(prospect_id)
