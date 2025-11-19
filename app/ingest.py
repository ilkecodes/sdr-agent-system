#!/usr/bin/env python
import os
import sys
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
import ollama

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
MODEL = "all-MiniLM-L6-v2"  # Same as ingest
LLM_MODEL = "llama3.2"  # or "llama3.1", "mistral", etc.

assert DB_URL, "DATABASE_URL is required"

engine = create_engine(DB_URL, pool_pre_ping=True)

# Load local embedding model
print("🔄 Loading embedding model...")
embedding_model = SentenceTransformer(MODEL)
print(f"✅ Loaded {MODEL}\n")


def list_available_documents():
    """Show available documents to query."""
    sql = text("""
        SELECT 
            doc_id,
            MIN(metadata->>'filename') as filename,
            COUNT(*) as chunk_count
        FROM rag_chunks
        GROUP BY doc_id
        ORDER BY MIN((metadata->>'ingested_at')::bigint) DESC
    """)
    
    with engine.connect() as conn:
        results = conn.execute(sql).fetchall()
    
    if not results:
        print("📭 No documents in database. Run 'python app/ingest.py' first.\n")
        return []
    
    print("📚 Available Documents:")
    print("=" * 80)
    for i, (doc_id, filename, chunk_count) in enumerate(results, 1):
        print(f"  [{i}] {filename} ({chunk_count} chunks) - doc_id: {doc_id[:16]}...")
    print("=" * 80)
    print()
    
    return results


def embed_query(query: str) -> list[float]:
    """Convert question to embedding vector locally."""
    embedding = embedding_model.encode([query], show_progress_bar=False)[0]
    return embedding.tolist()


def search_similar_chunks(query_embedding: list[float], top_k: int = 5, doc_id: str = None, filename: str = None):
    """Find most similar chunks using vector similarity (L2 distance)."""
    
    # Base query
    where_clause = ""
    params = {"query_embedding": str(query_embedding), "top_k": top_k}
    
    # Add filtering
    if doc_id:
        where_clause = "WHERE doc_id = :doc_id"
        params["doc_id"] = doc_id
    elif filename:
        where_clause = "WHERE metadata->>'filename' ILIKE :filename"
        params["filename"] = f"%{filename}%"
    
    sql = text(f"""
        SELECT 
            content,
            metadata,
            embedding <-> :query_embedding AS distance
        FROM rag_chunks
        {where_clause}
        ORDER BY embedding <-> :query_embedding
        LIMIT :top_k
    """)
    
    with engine.connect() as conn:
        results = conn.execute(sql, params).fetchall()
    
    return results


def generate_answer(question: str, context_chunks: list) -> str:
    """Use local Ollama LLM to generate answer based on retrieved context."""
    
    # Build context from retrieved chunks
    context = "\n\n---\n\n".join([
        f"[Chunk {i+1}]\n{row[0]}" 
        for i, row in enumerate(context_chunks)
    ])
    
    # Build prompt
    prompt = f"""You are a helpful assistant that answers questions based on the provided context.
Only use information from the context provided. If the answer is not in the context, say so.
Be concise and accurate.

Context:
{context}

Question: {question}

Answer:"""
    
    # Call local Ollama LLM
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response['message']['content']


def ask(question: str, top_k: int = 5, doc_id: str = None, filename: str = None, verbose: bool = True):
    """Main RAG query function."""
    
    if verbose:
        print(f"🔍 Question: {question}")
        if doc_id:
            print(f"📄 Filtering by doc_id: {doc_id[:16]}...")
        elif filename:
            print(f"📄 Filtering by filename: {filename}")
        else:
            print(f"📄 Searching ALL documents")
        print()
    
    # Step 1: Embed the question
    if verbose:
        print("📊 Embedding question...")
    query_embedding = embed_query(question)
    
    # Step 2: Search for similar chunks
    if verbose:
        print(f"🔎 Searching for top {top_k} relevant chunks...")
    results = search_similar_chunks(query_embedding, top_k, doc_id, filename)
    
    if not results:
        msg = "❌ No matching chunks found."
        if doc_id or filename:
            msg += " Try removing the document filter."
        return msg
    
    if verbose:
        print(f"✅ Found {len(results)} chunks\n")
        for i, row in enumerate(results):
            distance = row[2]
            preview = row[0][:100].replace('\n', ' ')
            print(f"  [{i+1}] distance={distance:.3f} | {preview}...")
        print()
    
    # Step 3: Generate answer using local LLM
    if verbose:
        print(f"💬 Generating answer with {LLM_MODEL}...\n")
    answer = generate_answer(question, results)
    
    if verbose:
        print("=" * 60)
        print("ANSWER:")
        print("=" * 60)
    print(answer)
    print()
    
    return answer


def interactive_mode():
    """Interactive query loop with document selection."""
    print("=" * 60)
    print("RAG Query System (100% Local)")
    print("=" * 60)
    print()
    
    # Show available documents
    docs = list_available_documents()
    if not docs:
        return
    
    # Ask if user wants to filter by document
    print("Options:")
    print("  1. Search ALL documents")
    print("  2. Search a specific document")
    print()
    
    choice = input("Choose option (1 or 2): ").strip()
    
    doc_id = None
    filename = None
    
    if choice == "2":
        print("\nEnter document number or filename:")
        selection = input("> ").strip()
        
        # Check if it's a number (selecting from list)
        if selection.isdigit():
            idx = int(selection) - 1
            if 0 <= idx < len(docs):
                doc_id = docs[idx][0]
                filename = docs[idx][1]
                print(f"✅ Selected: {filename}\n")
            else:
                print("❌ Invalid selection. Searching all documents.\n")
        else:
            # User typed a filename
            filename = selection
            print(f"✅ Filtering by filename: {filename}\n")
    else:
        print("✅ Searching ALL documents\n")
    
    print("Type your question (or 'quit' to exit, 'change' to change document)\n")
    
    while True:
        try:
            question = input("❓ Your question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("Goodbye! 👋")
                break
            
            if question.lower() in ['change', 'switch']:
                print("\nRestarting document selection...\n")
                interactive_mode()
                break
            
            print()
            ask(question, doc_id=doc_id, filename=filename)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")


def main():
    """Main entry point with CLI support."""
    
    # CLI mode
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print("""
RAG Query System - Usage

Interactive mode:
  python app/query.py
  
Command line mode:
  python app/query.py "your question here"
  python app/query.py "your question" --file "filename"
  python app/query.py "your question" --doc-id "abc123..."
  
Options:
  --file <filename>    Filter by filename (partial match)
  --doc-id <id>        Filter by exact doc_id
  --top-k <n>          Number of chunks to retrieve (default: 5)
  --list               List all documents and exit
  
Examples:
  python app/query.py "What is discussed in section 4?"
  python app/query.py "Who is the author?" --file "CV.pdf"
  python app/query.py "Summarize the main points" --top-k 10
            """)
            return
        
        if sys.argv[1] == "--list":
            list_available_documents()
            return
        
        # Parse CLI arguments
        question = sys.argv[1]
        doc_id = None
        filename = None
        top_k = 5
        
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--file" and i + 1 < len(sys.argv):
                filename = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--doc-id" and i + 1 < len(sys.argv):
                doc_id = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--top-k" and i + 1 < len(sys.argv):
                top_k = int(sys.argv[i + 1])
                i += 2
            else:
                i += 1
        
        ask(question, top_k=top_k, doc_id=doc_id, filename=filename)
    
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()