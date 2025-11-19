#!/usr/bin/env python
import os
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


def embed_query(query: str) -> list[float]:
    """Convert question to embedding vector locally."""
    embedding = embedding_model.encode([query], show_progress_bar=False)[0]
    return embedding.tolist()


def search_similar_chunks(query_embedding: list[float], top_k: int = 5):
    """Find most similar chunks using vector similarity (L2 distance)."""
    sql = text("""
        SELECT 
            content,
            metadata,
            embedding <-> :query_embedding AS distance
        FROM rag_chunks
        ORDER BY embedding <-> :query_embedding
        LIMIT :top_k
    """)
    
    with engine.connect() as conn:
        results = conn.execute(
            sql, 
            {"query_embedding": str(query_embedding), "top_k": top_k}
        ).fetchall()
    
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


def ask(question: str, top_k: int = 5, verbose: bool = True):
    """Main RAG query function."""
    
    if verbose:
        print(f"🔍 Question: {question}\n")
    
    # Step 1: Embed the question
    if verbose:
        print("📊 Embedding question...")
    query_embedding = embed_query(question)
    
    # Step 2: Search for similar chunks
    if verbose:
        print(f"🔎 Searching for top {top_k} relevant chunks...")
    results = search_similar_chunks(query_embedding, top_k)
    
    if not results:
        return "❌ No documents found in the database. Please run ingestion first."
    
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


def main():
    """Interactive query loop."""
    print("=" * 60)
    print("RAG Query System (100% Local)")
    print("=" * 60)
    print("Type your question (or 'quit' to exit)\n")
    
    while True:
        try:
            question = input("❓ Your question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("Goodbye! 👋")
                break
            
            print()
            ask(question)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    main()