"""Typeform Integration: OAuth 2.0, form response fetching, and KB ingestion.

FR-KB-001: Allow Admin User to ingest knowledge by connecting a Typeform account.

This module handles:
- OAuth 2.0 authentication with Typeform
- Fetching form responses
- Parsing responses into knowledge base chunks
- Auto-ingesting form data as structured Q&A pairs
"""

from __future__ import annotations

import os
import json
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from urllib.parse import urlencode
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from app.convert import convert_file
from app.ingest_snippet import ingest_chunks

load_dotenv()

# Typeform API credentials (set in .env)
TYPEFORM_CLIENT_ID = os.getenv("TYPEFORM_CLIENT_ID")
TYPEFORM_CLIENT_SECRET = os.getenv("TYPEFORM_CLIENT_SECRET")
TYPEFORM_REDIRECT_URI = os.getenv("TYPEFORM_REDIRECT_URI", "http://localhost:8000/oauth/typeform/callback")

DB_URL = os.getenv("DATABASE_URL")
assert DB_URL, "DATABASE_URL is required"

engine = create_engine(DB_URL, pool_pre_ping=True)


class TypeformOAuth:
    """Handle Typeform OAuth 2.0 flow."""
    
    AUTHORIZE_URL = "https://api.typeform.com/oauth/authorize"
    TOKEN_URL = "https://api.typeform.com/oauth/token"
    
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
            "client_id": TYPEFORM_CLIENT_ID,
            "redirect_uri": TYPEFORM_REDIRECT_URI,
            "scope": "forms:read responses:read",
            "state": state or os.urandom(16).hex()
        }
        return f"{TypeformOAuth.AUTHORIZE_URL}?{urlencode(params)}"
    
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
            "client_id": TYPEFORM_CLIENT_ID,
            "client_secret": TYPEFORM_CLIENT_SECRET,
            "redirect_uri": TYPEFORM_REDIRECT_URI
        }
        
        response = requests.post(TypeformOAuth.TOKEN_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        # Store token in database
        TypeformOAuth.store_token(token_data)
        
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
            "client_id": TYPEFORM_CLIENT_ID,
            "client_secret": TYPEFORM_CLIENT_SECRET
        }
        
        response = requests.post(TypeformOAuth.TOKEN_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        TypeformOAuth.store_token(token_data)
        
        return token_data
    
    @staticmethod
    def store_token(token_data: Dict[str, Any]):
        """Store OAuth token in database."""
        sql = text("""
            INSERT INTO oauth_tokens (
                provider, access_token, refresh_token, expires_at, scope, created_at
            ) VALUES (
                'typeform', :access_token, :refresh_token, 
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
                "expires_in": token_data.get("expires_in", 7200),
                "scope": token_data.get("scope", "")
            })
    
    @staticmethod
    def get_token() -> Optional[str]:
        """Get valid access token from database (refresh if expired)."""
        sql = text("""
            SELECT access_token, refresh_token, expires_at 
            FROM oauth_tokens 
            WHERE provider = 'typeform'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        with engine.connect() as conn:
            result = conn.execute(sql).fetchone()
            
            if not result:
                return None
            
            access_token, refresh_token, expires_at = result
            
            # Check if expired
            if expires_at and datetime.now() >= expires_at:
                if refresh_token:
                    # Refresh token
                    new_token = TypeformOAuth.refresh_access_token(refresh_token)
                    return new_token["access_token"]
                return None
            
            return access_token


class TypeformClient:
    """Client for Typeform API operations."""
    
    BASE_URL = "https://api.typeform.com"
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize Typeform client.
        
        Args:
            access_token: OAuth access token (fetches from DB if not provided)
        """
        self.access_token = access_token or TypeformOAuth.get_token()
        if not self.access_token:
            raise ValueError("No valid Typeform access token found. Please authenticate first.")
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated API request."""
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        
        return response.json()
    
    def list_forms(self, page_size: int = 10) -> List[Dict[str, Any]]:
        """List all forms in the account."""
        data = self._request("GET", "/forms", params={"page_size": page_size})
        return data.get("items", [])
    
    def get_form(self, form_id: str) -> Dict[str, Any]:
        """Get form definition (questions, fields)."""
        return self._request("GET", f"/forms/{form_id}")
    
    def get_responses(
        self, 
        form_id: str, 
        page_size: int = 100,
        since: Optional[str] = None,
        until: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get form responses.
        
        Args:
            form_id: Form ID
            page_size: Number of responses per page
            since: ISO 8601 datetime to fetch responses after
            until: ISO 8601 datetime to fetch responses before
            
        Returns:
            List of response objects
        """
        params = {"page_size": page_size}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        
        data = self._request("GET", f"/forms/{form_id}/responses", params=params)
        return data.get("items", [])


class TypeformKBIngestion:
    """Ingest Typeform responses into knowledge base."""
    
    @staticmethod
    def parse_response_to_qa(form: Dict[str, Any], response: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Parse a single form response into Q&A pairs.
        
        Args:
            form: Form definition with fields
            response: Individual response
            
        Returns:
            List of {"question": "...", "answer": "..."} pairs
        """
        qa_pairs = []
        
        # Map field IDs to questions
        field_map = {}
        for field in form.get("fields", []):
            field_map[field["id"]] = field.get("title", field.get("ref", "Unknown"))
        
        # Extract answers
        for answer in response.get("answers", []):
            field_id = answer.get("field", {}).get("id")
            question = field_map.get(field_id, "Unknown Question")
            
            # Extract answer based on type
            answer_text = None
            answer_type = answer.get("type")
            
            if answer_type == "text":
                answer_text = answer.get("text")
            elif answer_type == "email":
                answer_text = answer.get("email")
            elif answer_type == "number":
                answer_text = str(answer.get("number"))
            elif answer_type == "boolean":
                answer_text = "Yes" if answer.get("boolean") else "No"
            elif answer_type == "choice":
                choice = answer.get("choice", {})
                answer_text = choice.get("label", choice.get("other"))
            elif answer_type == "choices":
                labels = [c.get("label") for c in answer.get("choices", {}).get("labels", [])]
                answer_text = ", ".join(labels)
            elif answer_type == "date":
                answer_text = answer.get("date")
            elif answer_type == "url":
                answer_text = answer.get("url")
            elif answer_type == "file_url":
                answer_text = answer.get("file_url")
            
            if answer_text:
                qa_pairs.append({
                    "question": question,
                    "answer": answer_text
                })
        
        return qa_pairs
    
    @staticmethod
    def responses_to_markdown(form_id: str, form: Dict[str, Any], responses: List[Dict[str, Any]]) -> str:
        """
        Convert form responses to Markdown format for ingestion.
        
        Args:
            form_id: Form ID
            form: Form definition
            responses: List of responses
            
        Returns:
            Markdown document with all Q&A pairs
        """
        lines = [
            f"# {form.get('title', 'Typeform Responses')}",
            "",
            f"**Form ID:** {form_id}",
            f"**Description:** {form.get('description', 'N/A')}",
            f"**Responses:** {len(responses)}",
            f"**Ingested:** {datetime.now().isoformat()}",
            "",
            "---",
            ""
        ]
        
        for i, response in enumerate(responses, 1):
            lines.append(f"## Response {i}")
            lines.append("")
            lines.append(f"**Submitted:** {response.get('submitted_at', 'N/A')}")
            lines.append("")
            
            qa_pairs = TypeformKBIngestion.parse_response_to_qa(form, response)
            
            for qa in qa_pairs:
                lines.append(f"### Q: {qa['question']}")
                lines.append("")
                lines.append(f"**A:** {qa['answer']}")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def ingest_form_responses(
        form_id: str, 
        out_dir: str = "/tmp/typeform_kb",
        auto_ingest: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch and ingest Typeform responses into knowledge base.
        
        Args:
            form_id: Typeform form ID
            out_dir: Directory for intermediate files
            auto_ingest: Automatically ingest to vector DB
            
        Returns:
            Ingestion result with paths and stats
        """
        os.makedirs(out_dir, exist_ok=True)
        
        # Initialize client
        client = TypeformClient()
        
        # Fetch form and responses
        form = client.get_form(form_id)
        responses = client.get_responses(form_id)
        
        # Convert to markdown
        md_content = TypeformKBIngestion.responses_to_markdown(form_id, form, responses)
        
        # Write markdown
        md_path = os.path.join(out_dir, f"typeform_{form_id}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        # Write as temporary file for convert_file
        temp_path = os.path.join(out_dir, f"typeform_{form_id}_temp.txt")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        # Use convert.py to chunk
        result = convert_file(
            source_uri=temp_path,
            out_dir=out_dir
        )
        
        # Ingest chunks if requested
        if auto_ingest:
            chunks_ingested = ingest_chunks(
                result["chunks_path"],
                database_url=DB_URL
            )
            result["chunks_ingested"] = chunks_ingested
        
        # Track in database
        TypeformKBIngestion._track_ingestion(form_id, form, len(responses), result)
        
        return {
            "form_id": form_id,
            "form_title": form.get("title"),
            "responses_count": len(responses),
            "md_path": md_path,
            "chunks_path": result.get("chunks_path"),
            "chunks_count": result.get("n_chunks"),
            "chunks_ingested": result.get("chunks_ingested", 0),
            "ingested_at": datetime.now().isoformat()
        }
    
    @staticmethod
    def _track_ingestion(form_id: str, form: Dict[str, Any], response_count: int, result: Dict[str, Any]):
        """Track Typeform ingestion in database."""
        sql = text("""
            INSERT INTO typeform_ingestions (
                form_id, form_title, response_count, chunks_count, 
                chunks_path, ingested_at
            ) VALUES (
                :form_id, :form_title, :response_count, :chunks_count,
                :chunks_path, NOW()
            )
            ON CONFLICT (form_id) DO UPDATE SET
                response_count = EXCLUDED.response_count,
                chunks_count = EXCLUDED.chunks_count,
                chunks_path = EXCLUDED.chunks_path,
                updated_at = NOW()
        """)
        
        with engine.begin() as conn:
            conn.execute(sql, {
                "form_id": form_id,
                "form_title": form.get("title", "Untitled Form"),
                "response_count": response_count,
                "chunks_count": result.get("n_chunks", 0),
                "chunks_path": result.get("chunks_path")
            })


# Convenience functions
def authenticate_typeform() -> str:
    """Get OAuth authorization URL for Typeform."""
    return TypeformOAuth.get_authorization_url()


def complete_typeform_oauth(code: str) -> Dict[str, Any]:
    """Complete OAuth flow with authorization code."""
    return TypeformOAuth.exchange_code_for_token(code)


def ingest_typeform(form_id: str, **kwargs) -> Dict[str, Any]:
    """Ingest Typeform responses into knowledge base."""
    return TypeformKBIngestion.ingest_form_responses(form_id, **kwargs)


def list_typeform_forms() -> List[Dict[str, Any]]:
    """List all Typeform forms."""
    client = TypeformClient()
    return client.list_forms()
