# 🚀 Push to GitHub - Complete Guide

## Option 1: Automated Setup (Recommended)

### Install GitHub CLI
```bash
brew install gh
```

### Authenticate
```bash
gh auth login
```

### Run Setup Script
```bash
cd /Users/ilkeileri/WisemateKnowledgeBase/rag-min
./setup_github.sh
```

The script will:
- ✅ Initialize git repository
- ✅ Create .gitignore
- ✅ Create initial commit
- ✅ Create GitHub repository
- ✅ Push code
- ✅ Open repository in browser

---

## Option 2: Manual Setup (If you prefer web UI)

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Fill in:
   - **Repository name**: `sdr-agent-system`
   - **Description**: `Knowledge Base-Powered SDR Agent: Autonomous sales development with RAG, lead qualification, and personalized outreach`
   - **Visibility**: Public (recommended for portfolio) or Private
   - **DO NOT** initialize with README (we have one)
3. Click "Create repository"

### Step 2: Initialize Local Git

```bash
cd /Users/ilkeileri/WisemateKnowledgeBase/rag-min

# Initialize git
git init

# Create .gitignore
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

# Copy the GitHub-ready README
cp README_GITHUB.md README.md

# Stage all files
git add .

# Create initial commit
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
```

### Step 3: Connect to GitHub

Replace `YOUR_USERNAME` with your GitHub username:

```bash
# Add remote
git remote add origin https://github.com/YOUR_USERNAME/sdr-agent-system.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

### Step 4: Add Topics/Tags (Optional)

On GitHub.com, go to your repository and add these topics:
- `rag`
- `llm`
- `ai`
- `sales`
- `sdr`
- `automation`
- `knowledge-base`
- `python`
- `postgresql`
- `ollama`
- `gemini`
- `crm`
- `lead-generation`
- `personalization`

---

## Option 3: Quick Commands (For experienced users)

```bash
cd /Users/ilkeileri/WisemateKnowledgeBase/rag-min

# Install GitHub CLI (one-time)
brew install gh
gh auth login

# Create and push
./setup_github.sh
```

---

## What Gets Pushed

### Included:
- ✅ All source code (`app/`, `sql/`, `examples/`)
- ✅ Documentation (`docs/`)
- ✅ Setup scripts (`setup_sdr.sh`, `setup_github.sh`)
- ✅ Sample data (`data/sample_leads.csv`)
- ✅ Requirements (`requirements.txt`)
- ✅ README with badges and screenshots

### Excluded (via .gitignore):
- ❌ Virtual environment (`venv/`)
- ❌ Environment variables (`.env`)
- ❌ Python cache files (`__pycache__/`)
- ❌ Database files
- ❌ IDE configs
- ❌ Real lead data (only sample CSV included)

---

## After Pushing

### Set Up Repository Settings

1. **Description**: Already set by script/manual setup
2. **Topics**: Add tags for discoverability
3. **About section**: 
   - Website: Your demo URL (if you deploy)
   - Topics: `rag`, `llm`, `ai`, `sales`, `sdr`, `automation`

### Add Badges (Optional)

The README already includes:
- Python version badge
- PostgreSQL version badge
- License badge

### Create Releases

When you have a stable version:
```bash
git tag -a v1.0.0 -m "Initial release"
git push origin v1.0.0
```

### Enable GitHub Actions (Future)

You can add CI/CD workflows in `.github/workflows/`:
- Run tests on push
- Lint code
- Build Docker images
- Deploy to cloud

---

## Troubleshooting

### "Permission denied"
```bash
# Make script executable
chmod +x setup_github.sh
```

### "Repository already exists"
```bash
# Use a different name or delete existing repo on GitHub
gh repo delete YOUR_USERNAME/sdr-agent-system --yes
# Then run setup_github.sh again
```

### "Authentication failed"
```bash
# Re-authenticate
gh auth logout
gh auth login
```

### "Git not initialized"
```bash
cd /Users/ilkeileri/WisemateKnowledgeBase/rag-min
git init
```

---

## Next Steps After Pushing

1. **Share your repo**: Add link to LinkedIn, portfolio, resume
2. **Add screenshots**: Create `screenshots/` folder with demo images
3. **Write blog post**: Document your journey building this
4. **Deploy demo**: Consider deploying to Render, Railway, or Vercel
5. **Get feedback**: Share with community, iterate based on feedback

---

## Repository Best Practices

### Good First README
- ✅ Clear description of what it does
- ✅ Quick start guide
- ✅ Architecture diagram
- ✅ Usage examples
- ✅ Screenshots/GIFs
- ✅ Badges for tech stack
- ✅ License

### Good Documentation
- ✅ Comprehensive guides in `docs/`
- ✅ Code comments explaining complex logic
- ✅ API reference
- ✅ Troubleshooting section

### Good Code Organization
- ✅ Clear folder structure
- ✅ Separation of concerns
- ✅ Reusable components
- ✅ Example scripts

---

## Your Repository URL

After setup, your repository will be at:
```
https://github.com/YOUR_USERNAME/sdr-agent-system
```

**Clone command for others:**
```bash
git clone https://github.com/YOUR_USERNAME/sdr-agent-system.git
cd sdr-agent-system
./setup_sdr.sh
```

---

## Questions?

If you run into issues:
1. Check the troubleshooting section above
2. Open an issue on GitHub
3. Review GitHub CLI docs: https://cli.github.com/manual/

---

**Ready to push? Choose your option above and let's get your project on GitHub! 🚀**
