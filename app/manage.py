#!/usr/bin/env python
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from tabulate import tabulate

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
assert DB_URL, "DATABASE_URL is required"

engine = create_engine(DB_URL, pool_pre_ping=True)


def list_documents():
    """List all ingested documents with metadata."""
    sql = text("""
        SELECT 
            doc_id,
            COUNT(*) as chunk_count,
            MIN(metadata->>'filename') as filename,
            MIN(metadata->>'source') as source,
            MIN((metadata->>'ingested_at')::bigint) as ingested_at
        FROM rag_chunks
        GROUP BY doc_id
        ORDER BY ingested_at DESC
    """)
    
    with engine.connect() as conn:
        results = conn.execute(sql).fetchall()
    
    if not results:
        print("📭 No documents found in database.\n")
        return []
    
    # Format for display
    table_data = []
    for row in results:
        doc_id, chunk_count, filename, source, ingested_at = row
        
        # Convert timestamp to readable date
        if ingested_at:
            date_str = datetime.fromtimestamp(ingested_at).strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_str = "Unknown"
        
        table_data.append([
            doc_id[:12] + "...",  # Truncate doc_id
            filename or "Unknown",
            source or "Unknown",
            chunk_count,
            date_str
        ])
    
    print("\n📚 Ingested Documents:")
    print("=" * 80)
    print(tabulate(
        table_data,
        headers=["Doc ID", "Filename", "Source", "Chunks", "Ingested At"],
        tablefmt="simple"
    ))
    print("=" * 80)
    print(f"Total: {len(results)} document(s)\n")
    
    return results


def get_document_info(doc_id: str):
    """Get detailed information about a specific document."""
    
    # Get chunks for this document
    sql = text("""
        SELECT 
            chunk_id,
            content,
            metadata
        FROM rag_chunks
        WHERE doc_id = :doc_id
        ORDER BY chunk_id
    """)
    
    with engine.connect() as conn:
        results = conn.execute(sql, {"doc_id": doc_id}).fetchall()
    
    if not results:
        print(f"❌ Document '{doc_id}' not found.\n")
        return None
    
    # Parse metadata from first chunk
    metadata = json.loads(results[0][2])
    
    print("\n📄 Document Details:")
    print("=" * 80)
    print(f"Doc ID:       {doc_id}")
    print(f"Filename:     {metadata.get('filename', 'Unknown')}")
    print(f"Source:       {metadata.get('source', 'Unknown')}")
    print(f"Path:         {metadata.get('path', 'Unknown')}")
    print(f"Chunks:       {len(results)}")
    
    if metadata.get('ingested_at'):
        date_str = datetime.fromtimestamp(metadata['ingested_at']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Ingested:     {date_str}")
    
    print("=" * 80)
    
    # Show preview of chunks
    print("\n📝 Chunk Previews:")
    for i, row in enumerate(results[:5]):  # Show first 5 chunks
        chunk_id, content, _ = row
        preview = content[:150].replace('\n', ' ')
        print(f"  [{chunk_id}] {preview}...")
    
    if len(results) > 5:
        print(f"  ... and {len(results) - 5} more chunks")
    
    print()
    
    return results


def delete_document(doc_id: str, confirm: bool = True):
    """Delete a document and all its chunks."""
    
    # Check if document exists
    sql_check = text("SELECT COUNT(*) FROM rag_chunks WHERE doc_id = :doc_id")
    
    with engine.connect() as conn:
        count = conn.execute(sql_check, {"doc_id": doc_id}).scalar()
    
    if count == 0:
        print(f"❌ Document '{doc_id}' not found.\n")
        return False
    
    if confirm:
        print(f"⚠️  About to delete document '{doc_id}' ({count} chunks)")
        response = input("Are you sure? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ Deletion cancelled.\n")
            return False
    
    # Delete the document
    sql_delete = text("DELETE FROM rag_chunks WHERE doc_id = :doc_id")
    
    with engine.begin() as conn:
        conn.execute(sql_delete, {"doc_id": doc_id})
    
    print(f"✅ Deleted document '{doc_id}' ({count} chunks)\n")
    return True


def get_stats():
    """Show overall database statistics."""
    sql = text("""
        SELECT 
            COUNT(DISTINCT doc_id) as doc_count,
            COUNT(*) as chunk_count,
            AVG(pg_column_size(embedding)) as avg_embedding_size
        FROM rag_chunks
    """)
    
    with engine.connect() as conn:
        result = conn.execute(sql).fetchone()
    
    doc_count, chunk_count, avg_size = result
    
    print("\n📊 Database Statistics:")
    print("=" * 80)
    print(f"Total Documents:        {doc_count}")
    print(f"Total Chunks:           {chunk_count}")
    print(f"Avg Chunks per Doc:     {chunk_count / doc_count if doc_count > 0 else 0:.1f}")
    print(f"Avg Embedding Size:     {avg_size:.0f} bytes" if avg_size else "N/A")
    print("=" * 80)
    print()


def search_documents(query: str):
    """Search for documents by filename."""
    sql = text("""
        SELECT DISTINCT
            doc_id,
            metadata->>'filename' as filename,
            COUNT(*) OVER (PARTITION BY doc_id) as chunk_count
        FROM rag_chunks
        WHERE metadata->>'filename' ILIKE :query
        ORDER BY filename
    """)
    
    with engine.connect() as conn:
        results = conn.execute(sql, {"query": f"%{query}%"}).fetchall()
    
    if not results:
        print(f"❌ No documents found matching '{query}'\n")
        return []
    
    print(f"\n🔍 Found {len(results)} document(s) matching '{query}':")
    print("=" * 80)
    
    for doc_id, filename, chunk_count in results:
        print(f"  {doc_id[:16]}... | {filename} ({chunk_count} chunks)")
    
    print("=" * 80)
    print()
    
    return results


def main():
    """Interactive document management CLI."""
    import sys
    
    if len(sys.argv) < 2:
        print("""
📚 Document Management Tool

Usage:
  python app/manage.py list                    # List all documents
  python app/manage.py stats                   # Show statistics
  python app/manage.py info <doc_id>           # Show document details
  python app/manage.py delete <doc_id>         # Delete a document
  python app/manage.py search <query>          # Search by filename
  
Examples:
  python app/manage.py list
  python app/manage.py info a1b2c3d4e5f6g7h8
  python app/manage.py delete a1b2c3d4e5f6g7h8
  python app/manage.py search "CV.pdf"
        """)
        return
    
    command = sys.argv[1].lower()
    
    try:
        if command == "list":
            list_documents()
        
        elif command == "stats":
            get_stats()
        
        elif command == "info":
            if len(sys.argv) < 3:
                print("❌ Error: doc_id required\n")
                print("Usage: python app/manage.py info <doc_id>\n")
                return
            doc_id = sys.argv[2]
            get_document_info(doc_id)
        
        elif command == "delete":
            if len(sys.argv) < 3:
                print("❌ Error: doc_id required\n")
                print("Usage: python app/manage.py delete <doc_id>\n")
                return
            doc_id = sys.argv[2]
            delete_document(doc_id)
        
        elif command == "search":
            if len(sys.argv) < 3:
                print("❌ Error: search query required\n")
                print("Usage: python app/manage.py search <query>\n")
                return
            query = sys.argv[2]
            search_documents(query)
        
        else:
            print(f"❌ Unknown command: {command}\n")
            print("Run 'python app/manage.py' for usage help.\n")
    
    except Exception as e:
        print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    main()