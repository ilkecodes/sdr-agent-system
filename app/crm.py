"""CRM module: manage prospects, interactions, and campaigns."""

from __future__ import annotations

import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
assert DB_URL, "DATABASE_URL is required"

engine = create_engine(DB_URL, pool_pre_ping=True)


class ProspectManager:
    """Manage prospect lifecycle and data."""
    
    @staticmethod
    def create_prospect(
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company_name: Optional[str] = None,
        job_title: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        source: str = "manual",
        **kwargs
    ) -> int:
        """Create a new prospect. Returns prospect_id."""
        
        sql = text("""
            INSERT INTO prospects (
                email, first_name, last_name, company_name, job_title, 
                linkedin_url, source, created_at
            ) VALUES (
                :email, :first_name, :last_name, :company_name, :job_title,
                :linkedin_url, :source, now()
            )
            ON CONFLICT (email) DO UPDATE SET
                first_name = COALESCE(EXCLUDED.first_name, prospects.first_name),
                last_name = COALESCE(EXCLUDED.last_name, prospects.last_name),
                company_name = COALESCE(EXCLUDED.company_name, prospects.company_name),
                updated_at = now()
            RETURNING id
        """)
        
        with engine.begin() as conn:
            result = conn.execute(sql, {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "company_name": company_name,
                "job_title": job_title,
                "linkedin_url": linkedin_url,
                "source": source
            })
            return result.scalar()
    
    @staticmethod
    def get_prospect(prospect_id: int) -> Optional[Dict[str, Any]]:
        """Get prospect by ID."""
        sql = text("SELECT * FROM prospect_summary WHERE id = :id")
        
        with engine.connect() as conn:
            result = conn.execute(sql, {"id": prospect_id}).fetchone()
            if result:
                return dict(result._mapping)
            return None
    
    @staticmethod
    def update_prospect(prospect_id: int, **fields) -> bool:
        """Update prospect fields."""
        if not fields:
            return False
        
        # Build dynamic update
        set_clause = ", ".join(f"{k} = :{k}" for k in fields.keys())
        sql = text(f"""
            UPDATE prospects 
            SET {set_clause}, updated_at = now()
            WHERE id = :prospect_id
        """)
        
        with engine.begin() as conn:
            result = conn.execute(sql, {"prospect_id": prospect_id, **fields})
            return result.rowcount > 0
    
    @staticmethod
    def update_stage(prospect_id: int, stage: str, notes: Optional[str] = None):
        """Update prospect stage and optionally add notes."""
        fields = {"stage": stage}
        if notes:
            fields["notes"] = notes
        return ProspectManager.update_prospect(prospect_id, **fields)
    
    @staticmethod
    def update_score(prospect_id: int, score: float):
        """Update lead score (0-1)."""
        return ProspectManager.update_prospect(prospect_id, lead_score=max(0.0, min(1.0, score)))
    
    @staticmethod
    def list_prospects(
        stage: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List prospects with optional filters."""
        
        where_clauses = []
        params = {"limit": limit}
        
        if stage:
            where_clauses.append("stage = :stage")
            params["stage"] = stage
        
        if min_score is not None:
            where_clauses.append("lead_score >= :min_score")
            params["min_score"] = min_score
        
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        sql = text(f"""
            SELECT * FROM prospect_summary
            {where_sql}
            ORDER BY lead_score DESC, created_at DESC
            LIMIT :limit
        """)
        
        with engine.connect() as conn:
            results = conn.execute(sql, params).fetchall()
            return [dict(r._mapping) for r in results]
    
    @staticmethod
    def get_prospects_for_followup(limit: int = 20) -> List[Dict[str, Any]]:
        """Get prospects due for follow-up."""
        sql = text("""
            SELECT * FROM prospect_summary
            WHERE next_followup_at <= now()
              AND status = 'active'
              AND stage NOT IN ('closed_won', 'closed_lost')
            ORDER BY next_followup_at
            LIMIT :limit
        """)
        
        with engine.connect() as conn:
            results = conn.execute(sql, {"limit": limit}).fetchall()
            return [dict(r._mapping) for r in results]


class InteractionManager:
    """Track all prospect interactions."""
    
    @staticmethod
    def log_interaction(
        prospect_id: int,
        type: str,
        content: str,
        channel: str = "email",
        direction: str = "outbound",
        subject: Optional[str] = None,
        metadata: Optional[Dict] = None,
        agent_name: str = "sdr_agent"
    ) -> int:
        """Log an interaction. Returns interaction_id."""
        
        sql = text("""
            INSERT INTO interactions (
                prospect_id, type, channel, direction, subject, content,
                metadata, agent_name, status, created_at
            ) VALUES (
                :prospect_id, :type, :channel, :direction, :subject, :content,
                :metadata, :agent_name, 'sent', now()
            )
            RETURNING id
        """)
        
        with engine.begin() as conn:
            result = conn.execute(sql, {
                "prospect_id": prospect_id,
                "type": type,
                "channel": channel,
                "direction": direction,
                "subject": subject,
                "content": content,
                "metadata": json.dumps(metadata or {}),
                "agent_name": agent_name
            })
            
            # Update prospect's last_contacted_at
            if direction == "outbound":
                conn.execute(
                    text("UPDATE prospects SET last_contacted_at = now(), contact_attempts = contact_attempts + 1 WHERE id = :id"),
                    {"id": prospect_id}
                )
            
            return result.scalar()
    
    @staticmethod
    def get_interactions(prospect_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get interaction history for a prospect."""
        sql = text("""
            SELECT * FROM interactions
            WHERE prospect_id = :prospect_id
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        
        with engine.connect() as conn:
            results = conn.execute(sql, {"prospect_id": prospect_id, "limit": limit}).fetchall()
            return [dict(r._mapping) for r in results]


class ConversationManager:
    """Manage multi-turn conversations with prospects."""
    
    @staticmethod
    def create_conversation(prospect_id: int, initial_context: Optional[Dict] = None) -> int:
        """Start a new conversation. Returns conversation_id."""
        sql = text("""
            INSERT INTO conversations (prospect_id, messages, context, created_at)
            VALUES (:prospect_id, '[]'::jsonb, :context, now())
            RETURNING id
        """)
        
        with engine.begin() as conn:
            result = conn.execute(sql, {
                "prospect_id": prospect_id,
                "context": json.dumps(initial_context or {})
            })
            return result.scalar()
    
    @staticmethod
    def add_message(conversation_id: int, role: str, content: str):
        """Add a message to conversation (role: 'agent' or 'prospect')."""
        sql = text("""
            UPDATE conversations
            SET messages = messages || :new_message::jsonb,
                updated_at = now()
            WHERE id = :conversation_id
        """)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        with engine.begin() as conn:
            conn.execute(sql, {
                "conversation_id": conversation_id,
                "new_message": json.dumps([message])
            })
    
    @staticmethod
    def get_conversation(conversation_id: int) -> Optional[Dict[str, Any]]:
        """Get full conversation."""
        sql = text("SELECT * FROM conversations WHERE id = :id")
        
        with engine.connect() as conn:
            result = conn.execute(sql, {"id": conversation_id}).fetchone()
            if result:
                return dict(result._mapping)
            return None
    
    @staticmethod
    def update_context(conversation_id: int, context_updates: Dict):
        """Update conversation context (merge with existing)."""
        sql = text("""
            UPDATE conversations
            SET context = context || :updates::jsonb,
                updated_at = now()
            WHERE id = :conversation_id
        """)
        
        with engine.begin() as conn:
            conn.execute(sql, {
                "conversation_id": conversation_id,
                "updates": json.dumps(context_updates)
            })
    
    @staticmethod
    def get_active_conversation(prospect_id: int) -> Optional[Dict[str, Any]]:
        """Get active conversation for prospect."""
        sql = text("""
            SELECT * FROM conversations
            WHERE prospect_id = :prospect_id AND state = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
        """)
        
        with engine.connect() as conn:
            result = conn.execute(sql, {"prospect_id": prospect_id}).fetchone()
            if result:
                return dict(result._mapping)
            return None


class TemplateManager:
    """Manage message templates."""
    
    @staticmethod
    def get_template(template_id: int) -> Optional[Dict[str, Any]]:
        """Get template by ID."""
        sql = text("SELECT * FROM message_templates WHERE id = :id")
        
        with engine.connect() as conn:
            result = conn.execute(sql, {"id": template_id}).fetchone()
            if result:
                return dict(result._mapping)
            return None
    
    @staticmethod
    def render_template(template_id: int, variables: Dict[str, str]) -> Dict[str, str]:
        """Render template with variables."""
        template = TemplateManager.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        subject = template.get("subject", "")
        body = template["body"]
        
        # Simple variable substitution
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            subject = subject.replace(placeholder, value)
            body = body.replace(placeholder, value)
        
        return {"subject": subject, "body": body}


# Convenience functions
def get_prospect(prospect_id: int) -> Optional[Dict[str, Any]]:
    """Get prospect by ID."""
    return ProspectManager.get_prospect(prospect_id)


def create_prospect(email: str, **kwargs) -> int:
    """Create prospect."""
    return ProspectManager.create_prospect(email, **kwargs)


def log_interaction(prospect_id: int, type: str, content: str, **kwargs) -> int:
    """Log interaction."""
    return InteractionManager.log_interaction(prospect_id, type, content, **kwargs)
