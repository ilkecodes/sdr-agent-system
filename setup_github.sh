#!/bin/bash
# GitHub Repository Setup and Push Script

set -e  # Exit on error

echo "=========================================="
echo "🚀 GitHub Repository Setup"
echo "=========================================="
echo ""

# Configuration
REPO_NAME="sdr-agent-system"
REPO_DESCRIPTION="Knowledge Base-Powered SDR Agent: Autonomous sales development with RAG, lead qualification, and personalized outreach"
PROJECT_DIR="/Users/ilkeileri/WisemateKnowledgeBase/rag-min"

echo "📋 Repository Details:"
echo "   Name: $REPO_NAME"
echo "   Description: $REPO_DESCRIPTION"
echo "   Directory: $PROJECT_DIR"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) not found!"
    echo ""
    echo "Install with:"
    echo "  brew install gh"
    echo ""
    echo "Then authenticate:"
    echo "  gh auth login"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub!"
    echo ""
    echo "Run: gh auth login"
    exit 1
fi

echo "✅ GitHub CLI authenticated"
echo ""

# Navigate to project directory
cd "$PROJECT_DIR"

# Initialize git if needed
if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    echo "✅ Git initialized"
else
    echo "✅ Git already initialized"
fi

# Create .gitignore if it doesn't exist
if [ ! -f ".gitignore" ]; then
    echo "📝 Creating .gitignore..."
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv

# Environment variables
.env
.env.local

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Output directories
out/
output/
tmp/
/tmp/company_research/

# Logs
*.log

# Database
*.db
*.sqlite

# Jupyter
.ipynb_checkpoints/

# Test coverage
.coverage
htmlcov/

# Project specific
data/*.csv
!data/sample_leads.csv
EOF
    echo "✅ .gitignore created"
fi
echo ""

# Stage all files
echo "📦 Staging files..."
git add .
echo "✅ Files staged"
echo ""

# Check if there are changes to commit
if git diff --cached --quiet; then
    echo "⚠️  No changes to commit"
else
    # Commit
    echo "💾 Creating initial commit..."
    git commit -m "Initial commit: Knowledge Base-Powered SDR Agent System

Features:
- Triple-mode RAG (Local, Gemini, Hybrid)
- Full CRM with prospect lifecycle management
- Automated research & enrichment
- AI-powered personalization with KB integration
- Multi-channel outreach (Email, LinkedIn)
- Interactive chat interface
- Production-ready with safety & compliance features

Tech stack: Python, PostgreSQL+pgvector, Ollama, SentenceTransformers, Gemini API
"
    echo "✅ Initial commit created"
fi
echo ""

# Create GitHub repository
echo "🌐 Creating GitHub repository..."
echo ""
echo "Choose repository visibility:"
echo "  1) Public (recommended for portfolio)"
echo "  2) Private"
echo ""
read -p "Enter choice (1 or 2): " VISIBILITY_CHOICE

if [ "$VISIBILITY_CHOICE" = "1" ]; then
    VISIBILITY="public"
    VISIBILITY_FLAG="--public"
else
    VISIBILITY="private"
    VISIBILITY_FLAG="--private"
fi

echo ""
echo "Creating $VISIBILITY repository '$REPO_NAME'..."

if gh repo create "$REPO_NAME" $VISIBILITY_FLAG --description "$REPO_DESCRIPTION" --source=. --remote=origin --push; then
    echo ""
    echo "=========================================="
    echo "✅ Repository created successfully!"
    echo "=========================================="
    echo ""
    
    # Get the repository URL
    REPO_URL=$(gh repo view --json url -q .url)
    
    echo "🔗 Repository URL: $REPO_URL"
    echo ""
    echo "📚 Quick commands:"
    echo "   View repo:    gh repo view --web"
    echo "   Clone:        git clone $REPO_URL"
    echo "   Push changes: git push origin main"
    echo ""
    
    # Ask if user wants to add topics/tags
    echo "Would you like to add topics/tags to your repo? (y/n)"
    read -p "> " ADD_TOPICS
    
    if [ "$ADD_TOPICS" = "y" ] || [ "$ADD_TOPICS" = "Y" ]; then
        echo ""
        echo "Adding topics..."
        gh repo edit --add-topic "rag,llm,ai,sales,sdr,automation,knowledge-base,python,postgresql,ollama,gemini,crm,lead-generation,personalization"
        echo "✅ Topics added"
    fi
    
    echo ""
    echo "🎉 All done! Your project is now on GitHub!"
    echo ""
    
    # Open repository in browser
    echo "Opening repository in browser..."
    gh repo view --web
    
else
    echo ""
    echo "❌ Failed to create repository"
    echo ""
    echo "Possible issues:"
    echo "  - Repository name already exists"
    echo "  - Network connectivity"
    echo "  - GitHub API limits"
    echo ""
    echo "Manual alternative:"
    echo "  1. Create repo on GitHub.com"
    echo "  2. Run: git remote add origin https://github.com/YOUR_USERNAME/$REPO_NAME.git"
    echo "  3. Run: git push -u origin main"
    exit 1
fi
