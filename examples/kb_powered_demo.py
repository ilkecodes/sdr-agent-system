#!/usr/bin/env python
"""
Demo: Knowledge Base-Powered SDR Agent

Shows how the knowledge base powers every step of the SDR workflow:
1. Research: Auto-ingest prospect company data
2. Answer: Use RAG to answer product questions
3. Personalize: Draft emails using KB context
4. Track: See which KB sources were used
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tools import KnowledgeBaseTools, LeadEnrichment
from app.sdr_agent import SDRAgent
from app.crm import create_prospect, get_prospect
from dotenv import load_dotenv

load_dotenv()


def demo_kb_search():
    """Demo: Search knowledge base for product info."""
    print("\n" + "="*70)
    print("🔍 DEMO 1: Search Knowledge Base")
    print("="*70)
    
    queries = [
        "product features for enterprise customers",
        "pricing information",
        "customer success stories",
        "integration capabilities"
    ]
    
    for query in queries:
        print(f"\n📚 Query: \"{query}\"")
        results = KnowledgeBaseTools.search_knowledge(query, top_k=2)
        
        if results and 'error' not in results[0]:
            print(f"   ✅ Found {len(results)} relevant sources:")
            for r in results:
                preview = r['content'][:150].replace('\n', ' ')
                score = r['relevance_score']
                print(f"   - [Score: {score:.2f}] {preview}...")
        else:
            print("   ⚠️  No results found - please ingest documentation first")
            print("   Tip: Run `python -m app.ingest docs/` to populate KB")


def demo_kb_answer():
    """Demo: Answer questions using RAG."""
    print("\n" + "="*70)
    print("💬 DEMO 2: Answer Questions with RAG")
    print("="*70)
    
    questions = [
        "What are the main benefits of your product?",
        "Who are your typical customers?",
        "How does pricing work?"
    ]
    
    for question in questions:
        print(f"\n❓ Question: \"{question}\"")
        result = KnowledgeBaseTools.answer_from_knowledge(question, top_k=3)
        
        if 'error' not in result:
            print(f"\n   Answer: {result['answer'][:300]}...")
            print(f"\n   📖 Sources used: {len(result.get('sources', []))}")
        else:
            print(f"   ⚠️  Error: {result['error']}")
            print("   Tip: Ensure Ollama is running and documents are ingested")


def demo_company_research():
    """Demo: Research company and auto-ingest to KB."""
    print("\n" + "="*70)
    print("🏢 DEMO 3: Company Research → Knowledge Base")
    print("="*70)
    
    # Example company
    domain = "stripe.com"
    
    print(f"\n🔬 Researching: {domain}")
    print("   This will:")
    print("   1. Fetch company website")
    print("   2. Extract clean content")
    print("   3. Automatically add to knowledge base")
    print("   4. Enable KB queries about this company\n")
    
    try:
        result = LeadEnrichment.research_company(
            domain=domain,
            ingest_to_kb=True  # 🌟 Auto-add to KB
        )
        
        if result.get('scraped'):
            print(f"   ✅ Successfully researched {domain}")
            print(f"   📄 Content length: {len(result.get('description', ''))} chars")
            print(f"   📚 Ingested to KB: {result.get('ingested_to_kb', False)}")
            print(f"   🔗 Source: {result.get('source_url', 'N/A')}")
            
            # Now we can query about this company!
            print(f"\n   💡 Now you can ask: 'What does {domain} do?'")
            
        else:
            print(f"   ⚠️  Could not fetch {domain}: {result.get('error', 'Unknown error')}")
            print("   Note: Some sites block scraping (robots.txt)")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")


def demo_kb_powered_draft():
    """Demo: Draft email using KB context."""
    print("\n" + "="*70)
    print("✍️  DEMO 4: KB-Powered Email Drafting")
    print("="*70)
    
    # Create sample prospect
    print("\n📝 Creating sample prospect...")
    prospect_id = create_prospect(
        email="demo@example.com",
        first_name="Alex",
        last_name="Demo",
        company_name="Example Corp",
        job_title="VP of Sales",
        industry="SaaS",
        company_size="51-200"
    )
    
    print(f"   ✅ Created prospect #{prospect_id}")
    
    # Draft email (will search KB automatically)
    print("\n✍️  Drafting email...")
    print("   Agent will:")
    print("   1. Search KB for 'product benefits for SaaS VP of Sales'")
    print("   2. Find relevant case studies/features")
    print("   3. Draft personalized email citing KB sources")
    print()
    
    agent = SDRAgent()
    
    try:
        draft = agent.draft_outreach(
            prospect_id=prospect_id,
            channel="email"
        )
        
        if 'error' not in draft:
            print("\n" + "─"*70)
            print(f"Subject: {draft.get('subject', 'N/A')}")
            print("─"*70)
            print(draft.get('body', 'N/A'))
            print("─"*70)
            
            kb_sources = draft.get('kb_sources_available', 0)
            print(f"\n📚 Knowledge Base Sources Used: {kb_sources}")
            
            if kb_sources == 0:
                print("\n⚠️  Note: No KB sources found. To improve personalization:")
                print("   1. Ingest product documentation: `python -m app.ingest docs/`")
                print("   2. Add case studies for SaaS industry")
                print("   3. Include pricing/feature documentation")
        else:
            print(f"   ❌ Error: {draft['error']}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")


def demo_kb_stats():
    """Show knowledge base statistics."""
    print("\n" + "="*70)
    print("📊 Knowledge Base Statistics")
    print("="*70)
    
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(os.getenv("DATABASE_URL"))
        
        with engine.connect() as conn:
            # Count chunks
            chunks = conn.execute(text("SELECT COUNT(*) FROM rag_chunks")).scalar()
            print(f"\n   📄 Total chunks in knowledge base: {chunks}")
            
            if chunks == 0:
                print("\n   ⚠️  Knowledge base is empty!")
                print("\n   To populate:")
                print("   1. Add documents: `python -m app.ingest docs/`")
                print("   2. Parse websites: `python -m app.web_parse https://example.com`")
                print("   3. Import case studies: `python -m app.pipeline case_studies/`")
            else:
                # Show sample metadata
                sample = conn.execute(text("""
                    SELECT metadata->>'source_uri' as source, COUNT(*) as chunks
                    FROM rag_chunks
                    WHERE metadata IS NOT NULL
                    GROUP BY metadata->>'source_uri'
                    ORDER BY chunks DESC
                    LIMIT 5
                """)).fetchall()
                
                if sample:
                    print("\n   📚 Top sources:")
                    for row in sample:
                        source = row[0] or 'unknown'
                        chunks = row[1]
                        print(f"      - {source}: {chunks} chunks")
                        
    except Exception as e:
        print(f"   ❌ Error: {e}")


def main():
    """Run all demos."""
    print("="*70)
    print("🌟 Knowledge Base-Powered SDR Agent Demo")
    print("="*70)
    print("\nThis demo shows how your knowledge base powers intelligent outreach.")
    print("The KB is the STAR - it ensures accuracy, personalization, and credibility.\n")
    
    # Check DB connection
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: DATABASE_URL not set")
        print("Run: export DATABASE_URL='postgresql+psycopg://rag:ragpw@localhost:5433/ragdb'")
        return
    
    # Run demos
    demo_kb_stats()
    demo_kb_search()
    demo_kb_answer()
    demo_company_research()
    demo_kb_powered_draft()
    
    # Final tips
    print("\n" + "="*70)
    print("✅ Demo Complete!")
    print("="*70)
    print("\n🌟 Key Takeaways:")
    print("   1. Knowledge base powers every step of SDR workflow")
    print("   2. Auto-ingest prospect companies to enrich KB")
    print("   3. RAG ensures accurate answers (no hallucinations)")
    print("   4. Emails cite specific product benefits from your docs")
    print("   5. Sources are traceable for compliance")
    
    print("\n📚 Next Steps:")
    print("   1. Populate KB: `python -m app.ingest docs/`")
    print("   2. Test queries: `python -m app.query`")
    print("   3. Run workflow: `python examples/sdr_workflow.py`")
    print("   4. Read guide: `docs/KNOWLEDGE_BASE_INTEGRATION.md`")
    print()


if __name__ == "__main__":
    main()
