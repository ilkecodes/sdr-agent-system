"""Campaign Management and Trigger System.

FR-CRM-003: Campaign-triggered contact data fetching
FR-CRM-004: Store temporary copy in operational database
FR-CRM-005: Generate briefings for triggered campaigns

This module handles:
- Campaign definition and configuration
- Trigger conditions (time-based, event-based, manual)
- Automated contact fetching from CRMs when triggered
- Queue management for agent outreach
- Campaign analytics and reporting
"""

from __future__ import annotations

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from app.crm import ProspectManager
from app.hubspot_integration import HubSpotSync, HubSpotClient
from app.salesforce_integration import SalesforceSync, SalesforceClient

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
assert DB_URL, "DATABASE_URL is required"

engine = create_engine(DB_URL, pool_pre_ping=True)


class TriggerType(str, Enum):
    """Campaign trigger types."""
    MANUAL = "manual"  # Admin manually triggers
    SCHEDULED = "scheduled"  # Time-based (daily, weekly, etc.)
    EVENT = "event"  # External event (new lead, stage change, etc.)
    WEBHOOK = "webhook"  # Webhook from CRM


class CampaignStatus(str, Enum):
    """Campaign status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class CampaignManager:
    """Manage campaign lifecycle and triggers."""
    
    @staticmethod
    def create_campaign(
        name: str,
        description: Optional[str] = None,
        trigger_type: str = TriggerType.MANUAL,
        trigger_config: Optional[Dict[str, Any]] = None,
        crm_source: str = "hubspot",  # or "salesforce"
        crm_filters: Optional[Dict[str, Any]] = None,
        max_prospects: int = 100,
        agent_config: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Create a new campaign.
        
        Args:
            name: Campaign name
            description: Campaign description
            trigger_type: Type of trigger (manual, scheduled, event, webhook)
            trigger_config: Trigger-specific configuration
            crm_source: Source CRM (hubspot or salesforce)
            crm_filters: Filters for fetching contacts from CRM
            max_prospects: Maximum prospects to import per trigger
            agent_config: Agent behavior configuration
            
        Returns:
            campaign_id
        """
        sql = text("""
            INSERT INTO campaigns (
                name, description, trigger_type, trigger_config,
                crm_source, crm_filters, max_prospects, agent_config,
                status, created_at
            ) VALUES (
                :name, :description, :trigger_type, :trigger_config,
                :crm_source, :crm_filters, :max_prospects, :agent_config,
                'draft', NOW()
            )
            RETURNING id
        """)
        
        with engine.begin() as conn:
            result = conn.execute(sql, {
                "name": name,
                "description": description,
                "trigger_type": trigger_type,
                "trigger_config": json.dumps(trigger_config or {}),
                "crm_source": crm_source,
                "crm_filters": json.dumps(crm_filters or {}),
                "max_prospects": max_prospects,
                "agent_config": json.dumps(agent_config or {})
            })
            return result.scalar()
    
    @staticmethod
    def get_campaign(campaign_id: int) -> Optional[Dict[str, Any]]:
        """Get campaign by ID."""
        sql = text("SELECT * FROM campaigns WHERE id = :id")
        
        with engine.connect() as conn:
            result = conn.execute(sql, {"id": campaign_id}).fetchone()
            if result:
                return dict(result._mapping)
            return None
    
    @staticmethod
    def update_campaign(campaign_id: int, **fields) -> bool:
        """Update campaign fields."""
        if not fields:
            return False
        
        # Build dynamic update
        set_clause = ", ".join(f"{k} = :{k}" for k in fields.keys())
        sql = text(f"""
            UPDATE campaigns 
            SET {set_clause}, updated_at = NOW()
            WHERE id = :campaign_id
        """)
        
        with engine.begin() as conn:
            result = conn.execute(sql, {"campaign_id": campaign_id, **fields})
            return result.rowcount > 0
    
    @staticmethod
    def activate_campaign(campaign_id: int) -> bool:
        """Activate a campaign (make it live)."""
        return CampaignManager.update_campaign(campaign_id, status=CampaignStatus.ACTIVE)
    
    @staticmethod
    def pause_campaign(campaign_id: int) -> bool:
        """Pause an active campaign."""
        return CampaignManager.update_campaign(campaign_id, status=CampaignStatus.PAUSED)
    
    @staticmethod
    def list_campaigns(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List all campaigns with optional status filter."""
        where_clause = "WHERE status = :status" if status else ""
        sql = text(f"""
            SELECT * FROM campaigns
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        
        params = {"limit": limit}
        if status:
            params["status"] = status
        
        with engine.connect() as conn:
            results = conn.execute(sql, params).fetchall()
            return [dict(r._mapping) for r in results]


class CampaignTrigger:
    """Handle campaign trigger execution."""
    
    @staticmethod
    def trigger_campaign(campaign_id: int, triggered_by: str = "system") -> Dict[str, Any]:
        """
        Execute campaign trigger: fetch contacts and queue for outreach.
        
        Args:
            campaign_id: Campaign to trigger
            triggered_by: Who/what triggered (user_id, system, webhook)
            
        Returns:
            Trigger execution result with stats
        """
        # Get campaign config
        campaign = CampaignManager.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        if campaign["status"] != CampaignStatus.ACTIVE:
            raise ValueError(f"Campaign {campaign_id} is not active (status: {campaign['status']})")
        
        # Parse config
        crm_source = campaign["crm_source"]
        crm_filters = json.loads(campaign.get("crm_filters", "{}"))
        max_prospects = campaign["max_prospects"]
        
        # Fetch contacts from CRM
        prospect_ids = []
        
        if crm_source == "hubspot":
            prospect_ids = CampaignTrigger._fetch_from_hubspot(crm_filters, max_prospects)
        elif crm_source == "salesforce":
            prospect_ids = CampaignTrigger._fetch_from_salesforce(crm_filters, max_prospects)
        else:
            raise ValueError(f"Unknown CRM source: {crm_source}")
        
        # Log trigger execution
        execution_id = CampaignTrigger._log_execution(
            campaign_id=campaign_id,
            triggered_by=triggered_by,
            prospects_imported=len(prospect_ids),
            metadata={"crm_source": crm_source, "filters": crm_filters}
        )
        
        # Associate prospects with campaign
        for prospect_id in prospect_ids:
            CampaignTrigger._add_to_campaign_queue(campaign_id, prospect_id)
        
        return {
            "execution_id": execution_id,
            "campaign_id": campaign_id,
            "prospects_imported": len(prospect_ids),
            "prospect_ids": prospect_ids,
            "triggered_at": datetime.now().isoformat()
        }
    
    @staticmethod
    def _fetch_from_hubspot(filters: Dict[str, Any], limit: int) -> List[int]:
        """Fetch contacts from HubSpot based on filters."""
        # Convert filters to HubSpot search format
        hs_filters = []
        
        # Example filter formats:
        # {"lifecyclestage": "lead"} -> HubSpot filter
        # {"list_id": "123"} -> Fetch from list
        
        if "list_id" in filters:
            # Fetch from specific list
            client = HubSpotClient()
            contacts = client.get_contacts_by_list(filters["list_id"], limit=limit)
            prospect_ids = []
            for contact in contacts:
                contact_id = contact.get("vid") or contact.get("id")
                if contact_id:
                    prospect_id = HubSpotSync.import_contact(str(contact_id))
                    prospect_ids.append(prospect_id)
            return prospect_ids
        
        else:
            # Build search filters
            for key, value in filters.items():
                hs_filters.append({
                    "propertyName": key,
                    "operator": "EQ",
                    "value": value
                })
            
            # Use search API
            return HubSpotSync.import_contacts_by_filter(hs_filters, limit=limit)
    
    @staticmethod
    def _fetch_from_salesforce(filters: Dict[str, Any], limit: int) -> List[int]:
        """Fetch contacts/leads from Salesforce based on filters."""
        # Convert filters to SOQL
        # Example: {"Status": "Open", "Industry": "Technology"}
        
        if "campaign_id" in filters:
            # Import from Salesforce campaign
            return SalesforceSync.import_by_campaign(filters["campaign_id"], limit=limit)
        
        else:
            # Build SOQL query
            where_clauses = []
            for key, value in filters.items():
                where_clauses.append(f"{key} = '{value}'")
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Fetch leads
            client = SalesforceClient()
            soql = f"SELECT Id FROM Lead WHERE {where_sql} LIMIT {limit}"
            leads = client.query_leads(soql)
            
            prospect_ids = []
            for lead in leads:
                lead_id = lead.get("Id")
                if lead_id:
                    prospect_id = SalesforceSync.import_lead(lead_id)
                    prospect_ids.append(prospect_id)
            
            return prospect_ids
    
    @staticmethod
    def _log_execution(campaign_id: int, triggered_by: str, prospects_imported: int, metadata: Dict[str, Any]) -> int:
        """Log campaign trigger execution."""
        sql = text("""
            INSERT INTO campaign_executions (
                campaign_id, triggered_by, prospects_imported, 
                metadata, executed_at
            ) VALUES (
                :campaign_id, :triggered_by, :prospects_imported,
                :metadata, NOW()
            )
            RETURNING id
        """)
        
        with engine.begin() as conn:
            result = conn.execute(sql, {
                "campaign_id": campaign_id,
                "triggered_by": triggered_by,
                "prospects_imported": prospects_imported,
                "metadata": json.dumps(metadata)
            })
            return result.scalar()
    
    @staticmethod
    def _add_to_campaign_queue(campaign_id: int, prospect_id: int):
        """Add prospect to campaign outreach queue."""
        sql = text("""
            INSERT INTO campaign_queue (
                campaign_id, prospect_id, status, added_at
            ) VALUES (
                :campaign_id, :prospect_id, 'pending', NOW()
            )
            ON CONFLICT (campaign_id, prospect_id) DO NOTHING
        """)
        
        with engine.begin() as conn:
            conn.execute(sql, {
                "campaign_id": campaign_id,
                "prospect_id": prospect_id
            })


class CampaignScheduler:
    """Handle scheduled campaign triggers."""
    
    @staticmethod
    def check_scheduled_campaigns() -> List[Dict[str, Any]]:
        """
        Check for campaigns that need to be triggered based on schedule.
        
        This should be run periodically (e.g., every hour via cron).
        
        Returns:
            List of triggered campaign results
        """
        # Get active campaigns with scheduled triggers
        sql = text("""
            SELECT * FROM campaigns
            WHERE status = 'active'
              AND trigger_type = 'scheduled'
              AND (last_triggered_at IS NULL 
                   OR last_triggered_at < NOW() - trigger_config->>'interval'::INTERVAL)
        """)
        
        results = []
        
        with engine.connect() as conn:
            campaigns = conn.execute(sql).fetchall()
            
            for campaign in campaigns:
                campaign_dict = dict(campaign._mapping)
                campaign_id = campaign_dict["id"]
                
                try:
                    # Trigger campaign
                    result = CampaignTrigger.trigger_campaign(campaign_id, triggered_by="scheduler")
                    
                    # Update last triggered time
                    CampaignManager.update_campaign(campaign_id, last_triggered_at=datetime.now())
                    
                    results.append(result)
                    
                except Exception as e:
                    results.append({
                        "campaign_id": campaign_id,
                        "error": str(e),
                        "success": False
                    })
        
        return results
    
    @staticmethod
    def setup_campaign_schedule(
        campaign_id: int,
        interval: str = "1 day",  # PostgreSQL interval format
        start_time: Optional[datetime] = None
    ) -> bool:
        """
        Configure scheduled trigger for campaign.
        
        Args:
            campaign_id: Campaign to schedule
            interval: Interval between triggers (PostgreSQL interval syntax)
            start_time: When to start (defaults to now)
            
        Returns:
            Success boolean
        """
        trigger_config = {
            "interval": interval,
            "start_time": (start_time or datetime.now()).isoformat()
        }
        
        return CampaignManager.update_campaign(
            campaign_id,
            trigger_type=TriggerType.SCHEDULED,
            trigger_config=json.dumps(trigger_config)
        )


class CampaignQueue:
    """Manage campaign outreach queue."""
    
    @staticmethod
    def get_next_prospect(campaign_id: int) -> Optional[Dict[str, Any]]:
        """
        Get next prospect from campaign queue.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Prospect data or None if queue empty
        """
        sql = text("""
            SELECT cq.*, p.*
            FROM campaign_queue cq
            JOIN prospect_summary p ON cq.prospect_id = p.id
            WHERE cq.campaign_id = :campaign_id
              AND cq.status = 'pending'
            ORDER BY cq.added_at
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
        
        with engine.connect() as conn:
            result = conn.execute(sql, {"campaign_id": campaign_id}).fetchone()
            if result:
                return dict(result._mapping)
            return None
    
    @staticmethod
    def mark_prospect_processed(campaign_id: int, prospect_id: int, status: str = "processed"):
        """Mark prospect as processed in campaign queue."""
        sql = text("""
            UPDATE campaign_queue
            SET status = :status, processed_at = NOW()
            WHERE campaign_id = :campaign_id AND prospect_id = :prospect_id
        """)
        
        with engine.begin() as conn:
            conn.execute(sql, {
                "campaign_id": campaign_id,
                "prospect_id": prospect_id,
                "status": status
            })
    
    @staticmethod
    def get_queue_stats(campaign_id: int) -> Dict[str, Any]:
        """Get campaign queue statistics."""
        sql = text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'processed') as processed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed
            FROM campaign_queue
            WHERE campaign_id = :campaign_id
        """)
        
        with engine.connect() as conn:
            result = conn.execute(sql, {"campaign_id": campaign_id}).fetchone()
            return dict(result._mapping) if result else {}


# Convenience functions
def create_campaign(name: str, **kwargs) -> int:
    """Create a new campaign."""
    return CampaignManager.create_campaign(name, **kwargs)


def trigger_campaign(campaign_id: int, **kwargs) -> Dict[str, Any]:
    """Manually trigger a campaign."""
    return CampaignTrigger.trigger_campaign(campaign_id, **kwargs)


def get_campaign_stats(campaign_id: int) -> Dict[str, Any]:
    """Get campaign statistics."""
    return CampaignQueue.get_queue_stats(campaign_id)


def process_campaign_queue(campaign_id: int, agent_callback) -> int:
    """
    Process campaign queue with agent.
    
    Args:
        campaign_id: Campaign to process
        agent_callback: Function to call for each prospect (prospect_data) -> result
        
    Returns:
        Number of prospects processed
    """
    processed = 0
    
    while True:
        prospect = CampaignQueue.get_next_prospect(campaign_id)
        if not prospect:
            break
        
        try:
            # Call agent to process prospect
            agent_callback(prospect)
            
            # Mark as processed
            CampaignQueue.mark_prospect_processed(
                campaign_id,
                prospect["prospect_id"],
                status="processed"
            )
            processed += 1
            
        except Exception as e:
            # Mark as failed
            CampaignQueue.mark_prospect_processed(
                campaign_id,
                prospect["prospect_id"],
                status="failed"
            )
    
    return processed
