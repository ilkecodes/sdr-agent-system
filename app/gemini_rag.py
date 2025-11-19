"""Gemini File API integration for enhanced RAG capabilities.

This provides a hybrid approach:
- Local RAG (default): 100% local, private, free
- Gemini RAG (optional): Multimodal, fast, managed, with citations

Usage:
    from app.gemini_rag import GeminiRAG
    
    # Initialize
    rag = GeminiRAG(api_key=os.getenv("GOOGLE_API_KEY"))
    
    # Upload documents to corpus
    rag.create_corpus("product_docs", "Product documentation and features")
    rag.upload_file("product_docs", "docs/features.pdf")
    
    # Query with automatic citations
    result = rag.query("What are the key features?", corpus_name="product_docs")
    print(result['answer'])
    for citation in result['citations']:
        print(f"  Source: {citation['source']}")
"""

from __future__ import annotations

import os
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
import mimetypes

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class GeminiRAG:
    """Hybrid RAG system using Google's Gemini File API.
    
    Features:
    - Automatic chunking and embedding
    - Multimodal document support (PDF, images, code, DOCX)
    - Built-in citations
    - Parallel corpus search
    - Managed vector storage
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-pro-002",
        embedding_model: str = "models/text-embedding-004"
    ):
        """Initialize Gemini RAG.
        
        Args:
            api_key: Google API key (or set GOOGLE_API_KEY env var)
            model: Gemini model for generation
            embedding_model: Model for embeddings
        """
        if not GENAI_AVAILABLE:
            raise ImportError(
                "google-generativeai not installed. "
                "Run: pip install google-generativeai"
            )
        
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key required. Set GOOGLE_API_KEY env var or pass api_key"
            )
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model)
        self.embedding_model = embedding_model
        
        # Cache corpora
        self._corpora = {}
        self._refresh_corpora()
    
    def _refresh_corpora(self):
        """Refresh corpora cache."""
        try:
            corpora = genai.list_corpora()
            self._corpora = {c.name.split('/')[-1]: c for c in corpora}
        except Exception as e:
            print(f"Warning: Could not list corpora: {e}")
    
    def create_corpus(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new document corpus.
        
        Args:
            name: Unique corpus identifier
            display_name: Human-readable name
            description: Optional description
            
        Returns:
            Corpus metadata
        """
        try:
            corpus = genai.create_corpus(
                name=name,
                display_name=display_name,
                description=description or display_name
            )
            
            self._corpora[name] = corpus
            
            return {
                "name": corpus.name,
                "display_name": corpus.display_name,
                "description": corpus.description,
                "created": True
            }
            
        except Exception as e:
            # Corpus might already exist
            self._refresh_corpora()
            if name in self._corpora:
                return {
                    "name": self._corpora[name].name,
                    "display_name": self._corpora[name].display_name,
                    "already_exists": True
                }
            raise e
    
    def upload_file(
        self,
        corpus_name: str,
        file_path: str,
        display_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Upload file to corpus for indexing.
        
        Supported formats: PDF, DOCX, TXT, JSON, code files, images
        
        Args:
            corpus_name: Target corpus
            file_path: Path to file
            display_name: Optional display name
            metadata: Optional metadata dict
            
        Returns:
            Upload result with file info
        """
        if corpus_name not in self._corpora:
            raise ValueError(f"Corpus '{corpus_name}' not found. Create it first.")
        
        corpus = self._corpora[corpus_name]
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        # Upload to Gemini
        print(f"📤 Uploading {path.name} to corpus '{corpus_name}'...")
        
        try:
            uploaded_file = genai.upload_file(
                path=file_path,
                mime_type=mime_type,
                display_name=display_name or path.name
            )
            
            # Wait for processing
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(1)
                uploaded_file = genai.get_file(uploaded_file.name)
            
            if uploaded_file.state.name == "FAILED":
                raise Exception(f"File processing failed: {uploaded_file.error}")
            
            # Create document in corpus
            document = genai.create_document(
                corpus_name=corpus.name,
                display_name=display_name or path.name,
                file=uploaded_file
            )
            
            # Add custom metadata if provided
            if metadata:
                document.custom_metadata = metadata
            
            print(f"✅ Uploaded: {document.name}")
            
            return {
                "document_name": document.name,
                "file_name": path.name,
                "size_bytes": path.stat().st_size,
                "mime_type": mime_type,
                "state": uploaded_file.state.name,
                "metadata": metadata
            }
            
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            raise
    
    def upload_directory(
        self,
        corpus_name: str,
        directory: str,
        recursive: bool = True,
        extensions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Upload all files from directory to corpus.
        
        Args:
            corpus_name: Target corpus
            directory: Directory path
            recursive: Include subdirectories
            extensions: File extensions to include (e.g., ['.pdf', '.md'])
            
        Returns:
            Summary of uploads
        """
        path = Path(directory)
        if not path.is_dir():
            raise ValueError(f"Not a directory: {directory}")
        
        pattern = "**/*" if recursive else "*"
        files = path.glob(pattern)
        
        # Filter by extension if specified
        if extensions:
            files = [f for f in files if f.suffix.lower() in extensions]
        else:
            files = [f for f in files if f.is_file()]
        
        results = {
            "uploaded": [],
            "failed": [],
            "total": len(files)
        }
        
        for file_path in files:
            try:
                result = self.upload_file(
                    corpus_name=corpus_name,
                    file_path=str(file_path),
                    metadata={"source_dir": directory}
                )
                results["uploaded"].append(result)
            except Exception as e:
                results["failed"].append({
                    "file": str(file_path),
                    "error": str(e)
                })
        
        print(f"\n📊 Upload complete: {len(results['uploaded'])}/{results['total']} files")
        return results
    
    def query(
        self,
        question: str,
        corpus_name: Optional[str] = None,
        corpora: Optional[List[str]] = None,
        include_citations: bool = True,
        max_chunks: int = 10
    ) -> Dict[str, Any]:
        """Query corpus/corpora with automatic citation.
        
        Args:
            question: User question
            corpus_name: Single corpus to search (or use corpora for multiple)
            corpora: List of corpus names to search
            include_citations: Include citation metadata
            max_chunks: Max chunks to retrieve
            
        Returns:
            Answer with citations and sources
        """
        # Determine which corpora to search
        if corpus_name:
            search_corpora = [corpus_name]
        elif corpora:
            search_corpora = corpora
        else:
            # Search all available corpora
            search_corpora = list(self._corpora.keys())
        
        if not search_corpora:
            return {
                "answer": "No corpora available. Upload documents first.",
                "citations": []
            }
        
        # Build tool config for file search
        corpus_resources = []
        for name in search_corpora:
            if name in self._corpora:
                corpus_resources.append({
                    "corpus": self._corpora[name].name
                })
        
        if not corpus_resources:
            return {
                "answer": "Selected corpora not found.",
                "citations": []
            }
        
        # Configure file search tool
        tool_config = {
            "function_calling_config": {
                "mode": "auto"
            }
        }
        
        # Query with file search
        try:
            response = self.model.generate_content(
                question,
                tools=[{
                    "file_search": {
                        "corpora": corpus_resources
                    }
                }],
                tool_config=tool_config
            )
            
            # Extract answer
            answer = response.text
            
            # Extract citations from grounding metadata
            citations = []
            if include_citations and hasattr(response, 'grounding_metadata'):
                grounding = response.grounding_metadata
                
                # Parse grounding chunks
                if hasattr(grounding, 'grounding_chunks'):
                    for chunk in grounding.grounding_chunks:
                        if hasattr(chunk, 'retrieved_context'):
                            ctx = chunk.retrieved_context
                            citations.append({
                                "source": getattr(ctx, 'title', 'Unknown'),
                                "uri": getattr(ctx, 'uri', None),
                                "content_preview": getattr(ctx, 'text', '')[:200]
                            })
            
            return {
                "answer": answer,
                "citations": citations,
                "model": response.model_version,
                "corpora_searched": search_corpora
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "question": question
            }
    
    def hybrid_query(
        self,
        question: str,
        use_local: bool = True,
        use_gemini: bool = True,
        corpus_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Hybrid query using both local RAG and Gemini.
        
        Combines local knowledge base with Gemini's managed RAG for
        comprehensive results.
        
        Args:
            question: User question
            use_local: Include local RAG results
            use_gemini: Include Gemini results
            corpus_name: Gemini corpus to search
            
        Returns:
            Combined results from both systems
        """
        result = {
            "question": question,
            "local": None,
            "gemini": None,
            "combined_answer": None
        }
        
        # Query local RAG
        if use_local:
            try:
                from app import query as local_rag
                local_answer = local_rag.ask(question, verbose=False)
                result["local"] = {
                    "answer": local_answer,
                    "source": "local_pgvector"
                }
            except Exception as e:
                result["local"] = {"error": str(e)}
        
        # Query Gemini
        if use_gemini:
            gemini_result = self.query(question, corpus_name=corpus_name)
            result["gemini"] = gemini_result
        
        # Combine answers
        if result["local"] and result["gemini"]:
            combine_prompt = f"""You have two answers to the same question. Combine them into a comprehensive response.

Question: {question}

Local RAG Answer:
{result['local'].get('answer', 'N/A')}

Gemini Answer:
{result['gemini'].get('answer', 'N/A')}

Provide a unified answer that incorporates insights from both sources. If they contradict, note the discrepancy."""
            
            try:
                combined = self.model.generate_content(combine_prompt)
                result["combined_answer"] = combined.text
            except Exception as e:
                result["combined_answer"] = f"Error combining: {e}"
        
        return result
    
    def list_corpora(self) -> List[Dict[str, Any]]:
        """List all available corpora."""
        self._refresh_corpora()
        
        return [
            {
                "name": name,
                "display_name": corpus.display_name,
                "description": corpus.description
            }
            for name, corpus in self._corpora.items()
        ]
    
    def delete_corpus(self, corpus_name: str) -> bool:
        """Delete a corpus and all its documents."""
        if corpus_name not in self._corpora:
            return False
        
        try:
            genai.delete_corpus(self._corpora[corpus_name].name)
            del self._corpora[corpus_name]
            return True
        except Exception:
            return False


def main():
    """Demo of Gemini RAG integration."""
    import argparse
    from dotenv import load_dotenv
    
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Gemini File API RAG")
    parser.add_argument("--create-corpus", help="Create corpus with name")
    parser.add_argument("--upload", help="Upload file to corpus")
    parser.add_argument("--upload-dir", help="Upload directory to corpus")
    parser.add_argument("--corpus", help="Corpus name", default="default")
    parser.add_argument("--query", help="Query question")
    parser.add_argument("--hybrid", action="store_true", help="Use hybrid mode (local + Gemini)")
    parser.add_argument("--list", action="store_true", help="List corpora")
    
    args = parser.parse_args()
    
    try:
        rag = GeminiRAG()
        
        if args.list:
            corpora = rag.list_corpora()
            print("\n📚 Available Corpora:")
            for c in corpora:
                print(f"  - {c['name']}: {c['display_name']}")
        
        elif args.create_corpus:
            result = rag.create_corpus(
                name=args.create_corpus,
                display_name=args.create_corpus,
                description=f"Corpus created from CLI"
            )
            print(f"✅ Corpus created: {result['name']}")
        
        elif args.upload:
            result = rag.upload_file(args.corpus, args.upload)
            print(f"✅ Uploaded: {result['file_name']}")
        
        elif args.upload_dir:
            result = rag.upload_directory(args.corpus, args.upload_dir)
            print(f"✅ Uploaded {len(result['uploaded'])} files")
        
        elif args.query:
            if args.hybrid:
                result = rag.hybrid_query(args.query, corpus_name=args.corpus)
                print("\n🌟 HYBRID RESULT:")
                print("="*60)
                print(result.get('combined_answer', 'N/A'))
            else:
                result = rag.query(args.query, corpus_name=args.corpus)
                print("\n💬 ANSWER:")
                print("="*60)
                print(result.get('answer', 'N/A'))
                
                if result.get('citations'):
                    print("\n📖 CITATIONS:")
                    for i, cite in enumerate(result['citations'], 1):
                        print(f"  [{i}] {cite['source']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
