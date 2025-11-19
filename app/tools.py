"""Tool functions for SDR agent: research, enrichment, outreach."""

from __future__ import annotations

import os
import re
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
import time

# Import RAG infrastructure - THE STAR OF THE PROJECT
from app import query as rag_query
from app import web_parse

try:
    from app.gemini_rag import GeminiRAG
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    GeminiRAG = None


class LeadEnrichment:
    """Tools for enriching lead data from various sources."""
    
    @staticmethod
    def extract_domain_from_email(email: str) -> str:
        """Extract company domain from email."""
        if "@" in email:
            return email.split("@")[1]
        return ""
    
    @staticmethod
    def enrich_from_linkedin_url(linkedin_url: str) -> Dict[str, Any]:
        """
        Extract info from LinkedIn URL (mock implementation).
        In production, use LinkedIn API or a service like Apollo/Clearbit.
        """
        # Mock implementation - parse URL structure
        info = {
            "profile_url": linkedin_url,
            "extracted_at": datetime.now().isoformat()
        }
        
        # Try to extract name from URL pattern
        # e.g., linkedin.com/in/john-doe-12345
        match = re.search(r'/in/([^/?]+)', linkedin_url)
        if match:
            slug = match.group(1)
            # Convert john-doe to John Doe
            name_parts = slug.split('-')
            if len(name_parts) >= 2:
                info["first_name"] = name_parts[0].capitalize()
                info["last_name"] = name_parts[1].capitalize()
        
        return info
    
    @staticmethod
    def research_company(domain: str, ingest_to_kb: bool = True) -> Dict[str, Any]:
        """
        Research company from domain using web parsing.
        Parses website and optionally ingests into knowledge base.
        """
        info = {
            "domain": domain,
            "researched_at": datetime.now().isoformat()
        }
        
        # Try multiple URLs for company info
        urls_to_try = [
            f"https://{domain}/about",
            f"https://{domain}/company", 
            f"https://{domain}"
        ]
        
        parsed_content = None
        for url in urls_to_try:
            try:
                # Use web_parse to fetch and convert to markdown
                db_url = os.getenv("DATABASE_URL") if ingest_to_kb else None
                result = web_parse.parse_url(
                    url, 
                    out_dir="/tmp/company_research",
                    db_url=db_url,  # Automatically ingest to knowledge base!
                    fetch=True
                )
                
                # Read parsed markdown
                with open(result['md_path'], 'r', encoding='utf-8') as f:
                    parsed_content = f.read()
                
                info["source_url"] = url
                info["description"] = parsed_content[:1000]
                info["full_content_path"] = result['md_path']
                info["chunks_path"] = result.get('chunks_path')
                info["ingested_to_kb"] = ingest_to_kb
                info["scraped"] = True
                break  # Success, stop trying
                
            except Exception as e:
                info["last_error"] = str(e)
                continue  # Try next URL
        
        if not parsed_content:
            info["scraped"] = False
            info["error"] = f"Could not fetch any URL for {domain}"
        
        return info
    
    @staticmethod
    def find_tech_stack(domain: str) -> List[str]:
        """
        Detect technologies used by company.
        Uses BuiltWith-style detection (mock).
        """
        # Mock implementation
        # In production: use BuiltWith API or Wappalyzer
        
        common_stacks = {
            "saas": ["AWS", "React", "Node.js", "PostgreSQL"],
            "ecommerce": ["Shopify", "Stripe", "Google Analytics"],
            "enterprise": ["Salesforce", "Microsoft Azure", "Oracle"]
        }
        
        # Simple heuristic based on domain
        if "shop" in domain or "store" in domain:
            return common_stacks["ecommerce"]
        elif "enterprise" in domain or "corp" in domain:
            return common_stacks["enterprise"]
        else:
            return common_stacks["saas"]
    
    @staticmethod
    def search_news(company_name: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        Search recent news about company.
        Mock implementation - use NewsAPI or Google News in production.
        """
        # Mock news
        return [
            {
                "title": f"{company_name} announces new funding round",
                "source": "TechCrunch",
                "date": datetime.now().isoformat(),
                "url": f"https://techcrunch.com/{company_name.lower()}-funding"
            }
        ]


class OutreachTools:
    """Tools for sending outreach messages."""
    
    @staticmethod
    def send_email(
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Send email via SMTP.
        Set dry_run=False to actually send.
        """
        
        if dry_run:
            print(f"\n{'='*60}")
            print("📧 EMAIL (DRY RUN)")
            print(f"{'='*60}")
            print(f"To: {to}")
            print(f"From: {from_email or 'sdr@yourcompany.com'}")
            print(f"Subject: {subject}")
            print(f"\n{body}")
            print(f"{'='*60}\n")
            
            return {
                "status": "dry_run",
                "to": to,
                "subject": subject,
                "sent_at": datetime.now().isoformat()
            }
        
        # Real SMTP implementation
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_user = os.getenv("SMTP_USER")
            smtp_pass = os.getenv("SMTP_PASSWORD")
            
            if not smtp_user or not smtp_pass:
                raise ValueError("SMTP_USER and SMTP_PASSWORD env vars required for real sending")
            
            msg = MIMEMultipart()
            msg['From'] = from_email or smtp_user
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            
            return {
                "status": "sent",
                "to": to,
                "subject": subject,
                "sent_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "to": to
            }
    
    @staticmethod
    def send_linkedin_message(
        profile_url: str,
        message: str,
        connection_request: bool = False,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Send LinkedIn message or connection request.
        Requires LinkedIn automation tool or API in production.
        """
        
        if dry_run:
            print(f"\n{'='*60}")
            print("💼 LINKEDIN MESSAGE (DRY RUN)")
            print(f"{'='*60}")
            print(f"To: {profile_url}")
            print(f"Type: {'Connection Request' if connection_request else 'Direct Message'}")
            print(f"\n{message}")
            print(f"{'='*60}\n")
            
            return {
                "status": "dry_run",
                "profile_url": profile_url,
                "type": "connection_request" if connection_request else "message",
                "sent_at": datetime.now().isoformat()
            }
        
        # In production: use LinkedIn API or automation tool like Phantombuster
        return {
            "status": "not_implemented",
            "message": "LinkedIn automation requires API access or automation tool",
            "profile_url": profile_url
        }
    
    @staticmethod
    def schedule_followup(
        prospect_id: int,
        days_from_now: int,
        action: str = "send_followup"
    ) -> Dict[str, Any]:
        """Schedule a follow-up action."""
        from datetime import timedelta
        from app.crm import ProspectManager
        
        followup_date = datetime.now() + timedelta(days=days_from_now)
        
        ProspectManager.update_prospect(
            prospect_id,
            next_followup_at=followup_date
        )
        
        return {
            "prospect_id": prospect_id,
            "followup_date": followup_date.isoformat(),
            "action": action
        }


class KnowledgeBaseTools:
    """Tools for querying the RAG knowledge base - THE STAR OF THE PROJECT.
    
    Supports both:
    - Local RAG (default): 100% local, private, free
    - Gemini RAG (optional): Multimodal, fast, with citations
    """
    
    @staticmethod
    def search_knowledge(query: str, top_k: int = 5, use_gemini: bool = False, corpus_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search knowledge base for relevant documents.
        
        Args:
            query: Search query
            top_k: Number of results
            use_gemini: Use Gemini File API (requires GOOGLE_API_KEY)
            corpus_name: Gemini corpus name (if using Gemini)
            
        Returns:
            chunks with content, metadata, and similarity scores.
        """
        # Gemini mode
        if use_gemini and GEMINI_AVAILABLE:
            try:
                gemini = GeminiRAG()
                result = gemini.query(query, corpus_name=corpus_name, max_chunks=top_k)
                
                # Convert Gemini citations to our format
                chunks = []
                for i, cite in enumerate(result.get('citations', [])):
                    chunks.append({
                        "rank": i + 1,
                        "content": cite.get('content_preview', ''),
                        "metadata": {"source_uri": cite.get('uri'), "source": cite.get('source')},
                        "relevance_score": 0.9 - (i * 0.05),  # Approximate
                        "engine": "gemini"
                    })
                return chunks
            except Exception as e:
                return [{"error": f"Gemini search failed: {e}"}]
        
        # Local mode (default)
        try:
            # Embed query and search vector database
            query_embedding = rag_query.embed_query(query)
            results = rag_query.search_similar_chunks(query_embedding, top_k)
            
            # Format results
            chunks = []
            for i, row in enumerate(results):
                chunks.append({
                    "rank": i + 1,
                    "content": row[0],
                    "metadata": row[1],
                    "distance": float(row[2]),
                    "relevance_score": max(0, 1 - float(row[2])),  # Convert distance to similarity
                    "engine": "local"
                })
            
            return chunks
            
        except Exception as e:
            return [{"error": str(e)}]
    
    @staticmethod
    def answer_from_knowledge(question: str, top_k: int = 5, use_gemini: bool = False, corpus_name: Optional[str] = None, hybrid: bool = False) -> Dict[str, Any]:
        """
        Answer a question using RAG knowledge base.
        
        Args:
            question: Question to answer
            top_k: Number of chunks to retrieve
            use_gemini: Use Gemini File API
            corpus_name: Gemini corpus name
            hybrid: Combine local + Gemini for best results
            
        Returns:
            Answer with sources and citations
        """
        # Hybrid mode: combine local + Gemini
        if hybrid and GEMINI_AVAILABLE:
            try:
                gemini = GeminiRAG()
                result = gemini.hybrid_query(question, corpus_name=corpus_name)
                return {
                    "answer": result.get('combined_answer', result.get('gemini', {}).get('answer', 'N/A')),
                    "sources": result.get('gemini', {}).get('citations', []),
                    "question": question,
                    "mode": "hybrid",
                    "local_answer": result.get('local', {}).get('answer'),
                    "gemini_answer": result.get('gemini', {}).get('answer')
                }
            except Exception as e:
                # Fall back to local
                use_gemini = False
        
        # Gemini-only mode
        if use_gemini and GEMINI_AVAILABLE:
            try:
                gemini = GeminiRAG()
                result = gemini.query(question, corpus_name=corpus_name, max_chunks=top_k)
                return {
                    "answer": result.get('answer', 'N/A'),
                    "sources": result.get('citations', []),
                    "question": question,
                    "mode": "gemini"
                }
            except Exception as e:
                return {"error": f"Gemini query failed: {e}", "question": question}
        
        # Local mode (default)
        try:
            # Use full RAG pipeline
            answer = rag_query.ask(question, top_k=top_k, verbose=False)
            
            # Also get source chunks for transparency
            query_embedding = rag_query.embed_query(question)
            chunks = rag_query.search_similar_chunks(query_embedding, top_k)
            
            sources = []
            for row in chunks:
                metadata = row[1] or {}
                sources.append({
                    "content_preview": row[0][:200],
                    "source": metadata.get('source_uri', 'unknown'),
                    "distance": float(row[2])
                })
            
            return {
                "answer": answer,
                "sources": sources,
                "question": question,
                "mode": "local"
            }
            
        except Exception as e:
            return {"error": str(e), "question": question}


class ResearchTools:
    """Tools for researching prospects and companies."""
    
    @staticmethod
    def search_web(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Web search for prospect research.
        Uses DuckDuckGo or Google Custom Search in production.
        """
        # Mock implementation
        return [
            {
                "title": f"Result for {query}",
                "url": f"https://example.com/search?q={query}",
                "snippet": f"Information about {query}..."
            }
        ]
    
    @staticmethod
    def analyze_prospect_fit(prospect_data: Dict[str, Any], icp_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score prospect against Ideal Customer Profile (ICP).
        Returns score and reasoning.
        """
        score = 0.0
        reasons = []
        
        # Company size fit
        if "company_size" in icp_criteria and "company_size" in prospect_data:
            target_sizes = icp_criteria["company_size"]
            if prospect_data["company_size"] in target_sizes:
                score += 0.3
                reasons.append(f"Company size matches ({prospect_data['company_size']})")
        
        # Industry fit
        if "industries" in icp_criteria and "industry" in prospect_data:
            if prospect_data["industry"] in icp_criteria["industries"]:
                score += 0.3
                reasons.append(f"Industry match ({prospect_data['industry']})")
        
        # Job title fit
        if "job_titles" in icp_criteria and "job_title" in prospect_data:
            target_titles = icp_criteria["job_titles"]
            prospect_title = prospect_data["job_title"].lower()
            if any(title.lower() in prospect_title for title in target_titles):
                score += 0.2
                reasons.append(f"Job title relevant ({prospect_data['job_title']})")
        
        # Tech stack fit
        if "technologies" in icp_criteria and "technologies" in prospect_data:
            common_tech = set(icp_criteria["technologies"]) & set(prospect_data["technologies"])
            if common_tech:
                score += 0.2
                reasons.append(f"Uses relevant tech: {', '.join(common_tech)}")
        
        return {
            "score": min(1.0, score),
            "reasons": reasons,
            "fit_level": "high" if score > 0.7 else "medium" if score > 0.4 else "low"
        }


# Registry of all available tools for agent
TOOL_REGISTRY = {
    # Knowledge Base (THE STAR!) - Always check here first
    "search_knowledge": KnowledgeBaseTools.search_knowledge,
    "answer_from_knowledge": KnowledgeBaseTools.answer_from_knowledge,
    
    # Enrichment
    "enrich_linkedin": LeadEnrichment.enrich_from_linkedin_url,
    "research_company": LeadEnrichment.research_company,
    "find_tech_stack": LeadEnrichment.find_tech_stack,
    "search_news": LeadEnrichment.search_news,
    
    # Outreach
    "send_email": OutreachTools.send_email,
    "send_linkedin_message": OutreachTools.send_linkedin_message,
    "schedule_followup": OutreachTools.schedule_followup,
    
    # Research
    "search_web": ResearchTools.search_web,
    "analyze_fit": ResearchTools.analyze_prospect_fit,
}


def execute_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """Execute a tool by name with arguments."""
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool '{tool_name}' not found"}
    
    try:
        tool_func = TOOL_REGISTRY[tool_name]
        result = tool_func(**kwargs)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
