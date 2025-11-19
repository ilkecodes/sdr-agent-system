#!/usr/bin/env python
"""
Gemini File API Demo

Shows the power of Google's Gemini File API for multimodal RAG:
- Automatic chunking and embeddings
- Multimodal support (PDFs, images, code)
- Built-in citations
- Sub-2-second parallel search
- Hybrid mode with local RAG
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def check_setup():
    """Check if Gemini is set up."""
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("\n" + "="*70)
        print("⚠️  GOOGLE_API_KEY not set")
        print("="*70)
        print("\nTo use Gemini File API:")
        print("1. Get API key: https://aistudio.google.com/apikey")
        print("2. Add to .env: GOOGLE_API_KEY=your_key_here")
        print("\nFor now, the demo will use LOCAL RAG only.\n")
        return False
    
    try:
        from app.gemini_rag import GeminiRAG
        print("✅ Gemini File API available")
        return True
    except ImportError as e:
        print(f"⚠️  Gemini not available: {e}")
        print("Run: pip install google-generativeai")
        return False


def demo_local_vs_gemini():
    """Compare local RAG vs Gemini RAG."""
    print("\n" + "="*70)
    print("📊 DEMO: Local vs Gemini RAG")
    print("="*70)
    
    from app.tools import KnowledgeBaseTools
    
    question = "What are the key product features?"
    
    # Local search
    print(f"\n🔍 Question: {question}")
    print("\n1️⃣  LOCAL RAG:")
    print("-" * 70)
    
    local_results = KnowledgeBaseTools.search_knowledge(question, top_k=3)
    
    if local_results and 'error' not in local_results[0]:
        for r in local_results[:3]:
            print(f"   • {r['content'][:150]}...")
            print(f"     (relevance: {r['relevance_score']:.2f})")
    else:
        print("   ⚠️  No local results. Run: python -m app.ingest docs/")
    
    # Gemini search
    if check_setup():
        print("\n2️⃣  GEMINI RAG:")
        print("-" * 70)
        
        try:
            gemini_results = KnowledgeBaseTools.search_knowledge(
                question,
                top_k=3,
                use_gemini=True,
                corpus_name="product_docs"
            )
            
            if gemini_results and 'error' not in gemini_results[0]:
                for r in gemini_results[:3]:
                    print(f"   • {r['content'][:150]}...")
                    print(f"     Source: {r['metadata'].get('source', 'N/A')}")
            else:
                error = gemini_results[0].get('error', 'Unknown error')
                print(f"   ⚠️  {error}")
                print("   Create corpus: python -m app.gemini_rag --create-corpus product_docs")
                print("   Upload docs: python -m app.gemini_rag --corpus product_docs --upload-dir docs/")
        except Exception as e:
            print(f"   ❌ Error: {e}")


def demo_hybrid_mode():
    """Demo hybrid mode combining local + Gemini."""
    if not check_setup():
        print("\n⚠️  Skipping hybrid demo (Gemini not available)")
        return
    
    print("\n" + "="*70)
    print("🌟 DEMO: Hybrid Mode (Local + Gemini)")
    print("="*70)
    
    from app.tools import KnowledgeBaseTools
    
    question = "How does our pricing work?"
    
    print(f"\n❓ Question: {question}")
    print("\n🔄 Querying both local and Gemini, then combining...")
    
    try:
        result = KnowledgeBaseTools.answer_from_knowledge(
            question,
            hybrid=True,
            corpus_name="product_docs"
        )
        
        if 'error' not in result:
            print("\n" + "="*70)
            print("COMBINED ANSWER:")
            print("="*70)
            print(result['answer'])
            
            if result.get('local_answer'):
                print("\n📚 Local RAG Answer:")
                print(result['local_answer'][:300] + "...")
            
            if result.get('gemini_answer'):
                print("\n🤖 Gemini Answer:")
                print(result['gemini_answer'][:300] + "...")
        else:
            print(f"❌ Error: {result['error']}")
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_multimodal():
    """Demo multimodal capabilities (images, PDFs, code)."""
    if not check_setup():
        print("\n⚠️  Skipping multimodal demo (Gemini not available)")
        return
    
    print("\n" + "="*70)
    print("🎨 DEMO: Multimodal RAG (Images, PDFs, Code)")
    print("="*70)
    
    print("\nGemini File API supports:")
    print("  • 📄 PDFs (with embedded images)")
    print("  • 🖼️  Images (PNG, JPG, diagrams)")
    print("  • 💻 Code files (Python, JS, Java, etc.)")
    print("  • 📊 Presentations (PPTX)")
    print("  • 📝 Documents (DOCX)")
    
    print("\nExample usage:")
    print("""
    from app.gemini_rag import GeminiRAG
    
    rag = GeminiRAG()
    rag.create_corpus("visual_kb", "Visual Knowledge Base")
    
    # Upload architecture diagram
    rag.upload_file("visual_kb", "diagrams/architecture.png")
    
    # Upload code examples
    rag.upload_file("visual_kb", "examples/integration.py")
    
    # Query understands BOTH images and code!
    result = rag.query(
        "Explain the architecture and show me integration code",
        corpus_name="visual_kb"
    )
    """)


def demo_cost():
    """Show cost breakdown."""
    print("\n" + "="*70)
    print("💰 DEMO: Cost Comparison")
    print("="*70)
    
    print("\n📊 Pricing:")
    print("\nLocal RAG:")
    print("  • Setup: Free")
    print("  • Storage: Free (self-hosted Postgres)")
    print("  • Queries: Free (unlimited)")
    print("  • Total: $0")
    
    print("\nGemini File API:")
    print("  • Indexing: $0.15 per 1M tokens (one-time)")
    print("  • Storage: FREE")
    print("  • Query embeddings: FREE")
    print("  • LLM generation: Standard Gemini rates (~$0.001/query)")
    
    print("\n📈 Example Scenario:")
    print("  • 100 product docs (500 pages) = ~500K tokens")
    print("  • Indexing cost: $0.075 (one-time)")
    print("  • 1,000 queries/month: ~$1.00")
    print("  • Total: ~$1.08/month")
    
    print("\n💡 Recommendation:")
    print("  • Use LOCAL for: High-volume, routine queries")
    print("  • Use GEMINI for: Complex queries, multimodal content")
    print("  • Use HYBRID for: Critical prospect research")


def demo_setup_guide():
    """Show quick setup guide."""
    print("\n" + "="*70)
    print("🚀 Quick Setup Guide")
    print("="*70)
    
    print("\n1️⃣  Get Google API Key:")
    print("   https://aistudio.google.com/apikey")
    
    print("\n2️⃣  Add to .env:")
    print("   echo 'GOOGLE_API_KEY=your_key_here' >> .env")
    
    print("\n3️⃣  Create corpus:")
    print("   python -m app.gemini_rag --create-corpus product_docs")
    
    print("\n4️⃣  Upload documents:")
    print("   python -m app.gemini_rag --corpus product_docs --upload-dir docs/")
    
    print("\n5️⃣  Query with citations:")
    print("   python -m app.gemini_rag --corpus product_docs --query 'key features'")
    
    print("\n6️⃣  Use in SDR agent:")
    print("""
   from app.tools import KnowledgeBaseTools
   
   # Gemini-powered search
   results = KnowledgeBaseTools.search_knowledge(
       "product benefits for FinTech",
       use_gemini=True,
       corpus_name="product_docs"
   )
   
   # Hybrid mode (best results)
   answer = KnowledgeBaseTools.answer_from_knowledge(
       "Does our product integrate with Salesforce?",
       hybrid=True
   )
   """)


def main():
    """Run all demos."""
    print("="*70)
    print("🌟 Gemini File API Integration Demo")
    print("="*70)
    print("\nThis demo shows how Google's Gemini File API enhances your RAG system")
    print("with multimodal understanding, automatic chunking, and built-in citations.")
    
    # Check setup
    gemini_available = check_setup()
    
    # Run demos
    demo_local_vs_gemini()
    
    if gemini_available:
        demo_hybrid_mode()
        demo_multimodal()
    
    demo_cost()
    demo_setup_guide()
    
    # Final message
    print("\n" + "="*70)
    print("✅ Demo Complete!")
    print("="*70)
    
    if not gemini_available:
        print("\n💡 To unlock Gemini features:")
        print("   1. Get API key: https://aistudio.google.com/apikey")
        print("   2. Set GOOGLE_API_KEY in .env")
        print("   3. Run: python examples/gemini_demo.py")
    else:
        print("\n🚀 Next Steps:")
        print("   1. Upload your docs: python -m app.gemini_rag --upload-dir docs/")
        print("   2. Test queries: python -m app.gemini_rag --query 'your question'")
        print("   3. Enable in SDR: Use hybrid mode in agent")
        print("   4. Read guide: docs/GEMINI_INTEGRATION.md")
    
    print()


if __name__ == "__main__":
    main()
