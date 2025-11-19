#!/bin/bash
# Quick setup script for SDR Agent system

set -e

echo "========================================="
echo "SDR Agent System - Quick Setup"
echo "========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from example..."
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        cat > .env << 'EOF'
DATABASE_URL=postgresql+psycopg://rag:ragpw@localhost:5433/ragdb
LLM_MODEL=llama3.2
EXPECTED_EMBED_DIM=384

# Optional: for real email sending
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
EOF
    fi
    echo "✅ Created .env file"
else
    echo "✅ .env file exists"
fi

# Start database
echo ""
echo "🐘 Starting Postgres + pgvector..."
docker compose up -d

# Wait for DB to be ready
echo "⏳ Waiting for database to be ready..."
sleep 3

# Load environment
source .env

# Check if venv exists
if [ ! -d .venv ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt
pip install -q sentence-transformers ollama langdetect

echo "✅ Dependencies installed"

# Create CRM tables
echo ""
echo "🗄️  Creating CRM tables..."
psql $DATABASE_URL -f sql/prospects.sql > /dev/null 2>&1 || {
    echo "⚠️  CRM tables may already exist (this is okay)"
}

echo "✅ Database schema ready"

# Check if Ollama is installed
echo ""
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is installed"
    
    # Check if model is available
    if ollama list | grep -q "llama3.2"; then
        echo "✅ llama3.2 model is available"
    else
        echo "📥 Downloading llama3.2 model (this may take a while)..."
        ollama pull llama3.2
    fi
else
    echo "⚠️  Ollama not found. Install from: https://ollama.ai"
    echo "   Then run: ollama pull llama3.2"
fi

echo ""
echo "========================================="
echo "✅ Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Run demo workflow:"
echo "   python examples/sdr_workflow.py"
echo ""
echo "2. Interactive chat with agent:"
echo "   python examples/sdr_workflow.py --chat"
echo ""
echo "3. Import your own leads:"
echo "   python -m app.lead_finder import-csv your_leads.csv"
echo ""
echo "4. Read full documentation:"
echo "   cat docs/SDR_AGENT.md"
echo ""
echo "5. Manage prospects:"
echo "   python -m app.crm"
echo ""
