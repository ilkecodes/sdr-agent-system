CREATE EXTENSION IF NOT EXISTS vector;

-- 384 dims for SentenceTransformers `all-MiniLM-L6-v2` (local default)
CREATE TABLE IF NOT EXISTS rag_chunks (
  id        BIGSERIAL PRIMARY KEY,
  doc_id    TEXT NOT NULL,
  chunk_id  INT  NOT NULL,
  content   TEXT NOT NULL,
  metadata  JSONB NOT NULL,
  embedding vector(384) NOT NULL,
  UNIQUE (doc_id, chunk_id)
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_embed_hnsw
  ON rag_chunks USING hnsw (embedding vector_l2_ops);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc_id ON rag_chunks (doc_id);

-- Documents table stores full canonical markdown for provenance and easier document-level queries
CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY,
  title TEXT,
  md TEXT NOT NULL,
  metadata JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
