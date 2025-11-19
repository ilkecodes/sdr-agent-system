"""
Example: Complete SDR workflow for finding and engaging leads.

This demonstrates:
1. Finding leads in target domains
2. Enriching prospect data
3. Qualifying against ICP
4. Drafting personalized outreach
5. Sending emails/LinkedIn messages
"""

import os
import sys

# Mock example data - in production, import from CSV or API
EXAMPLE_LEADS = [
    {
        "email": "sarah.chen@techcorp.com",
        "first_name": "Sarah",
        "last_name": "Chen",
        "company_name": "TechCorp",
        "company_domain": "techcorp.com",
        "job_title": "VP of Sales",
        "industry": "SaaS",
        "company_size": "201-500",
        "linkedin_url": "https://linkedin.com/in/sarahchen"
    },
    {
        "email": "mike.johnson@cloudify.io",
        "first_name": "Mike",
        "last_name": "Johnson",
        "company_name": "Cloudify",
        "company_domain": "cloudify.io",
        "job_title": "Director of Marketing",
        "industry": "Technology",
        "company_size": "51-200",
        "linkedin_url": "https://linkedin.com/in/mikejohnson"
    },
    {
        "email": "lisa.wang@enterprise.com",
        "first_name": "Lisa",
        "last_name": "Wang",
        "company_name": "Enterprise Solutions",
        "company_domain": "enterprise.com",
        "job_title": "Chief Technology Officer",
        "industry": "Software",
        "company_size": "1001-5000",
        "linkedin_url": "https://linkedin.com/in/lisawang"
    }
]


def setup_database():
    """Initialize prospect tables if needed."""
    from sqlalchemy import create_engine, text
    from dotenv import load_dotenv
    
    load_dotenv()
    DB_URL = os.getenv("DATABASE_URL")
    
    if not DB_URL:
        print("❌ DATABASE_URL not set. Please set it in .env file")
        sys.exit(1)
    
    engine = create_engine(DB_URL)
    
    # Check if prospects table exists
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'prospects'
            )
        """))
        
        if not result.scalar():
            print("⚠️  Prospects table not found. Creating it now...")
            
            # Run prospects.sql
            with open("sql/prospects.sql", "r") as f:
                sql_commands = f.read()
            
            with engine.begin() as conn:
                # Split and execute each command
                for command in sql_commands.split(";"):
                    command = command.strip()
                    if command:
                        conn.execute(text(command))
            
            print("✅ Prospects tables created")
        else:
            print("✅ Database ready")


def import_leads():
    """Import example leads into CRM."""
    from app.crm import create_prospect
    
    print("\n" + "="*60)
    print("📥 STEP 1: Importing Leads")
    print("="*60)
    
    prospect_ids = []
    
    for lead in EXAMPLE_LEADS:
        try:
            prospect_id = create_prospect(**lead, source="demo")
            prospect_ids.append(prospect_id)
            print(f"✅ Imported: {lead['first_name']} {lead['last_name']} ({lead['email']})")
        except Exception as e:
            print(f"❌ Failed to import {lead['email']}: {e}")
    
    print(f"\n✅ Imported {len(prospect_ids)} leads")
    return prospect_ids


def run_sdr_workflow(prospect_ids, channel="email", dry_run=True):
    """Run SDR agent workflow on imported leads."""
    from app.sdr_agent import SDRAgent
    
    print("\n" + "="*60)
    print("🤖 STEP 2: Running SDR Agent Workflow")
    print("="*60)
    
    agent = SDRAgent(
        name="Demo SDR Agent",
        icp_criteria={
            "company_size": ["51-200", "201-500", "501-1000"],
            "industries": ["SaaS", "Technology", "Software"],
            "job_titles": ["VP", "Director", "Head of", "Chief"],
            "technologies": ["Salesforce", "HubSpot", "AWS", "Stripe"]
        }
    )
    
    results = []
    
    for prospect_id in prospect_ids:
        print(f"\n{'─'*60}")
        
        result = agent.run_full_workflow(
            prospect_id=prospect_id,
            channel=channel,
            dry_run=dry_run
        )
        results.append(result)
        
        # Small delay between prospects
        import time
        time.sleep(1)
    
    return results


def show_summary(results):
    """Show summary of workflow results."""
    print("\n" + "="*60)
    print("📊 WORKFLOW SUMMARY")
    print("="*60)
    
    total = len(results)
    qualified = sum(1 for r in results if r.get("qualification", {}).get("score", 0) > 0.6)
    reached_out = sum(1 for r in results if r.get("outreach", {}).get("status") == "dry_run")
    
    print(f"\nTotal Prospects: {total}")
    print(f"Qualified (score > 0.6): {qualified}")
    print(f"Outreach Sent: {reached_out}")
    
    print("\n" + "─"*60)
    print("PROSPECT SCORES:")
    print("─"*60)
    
    for i, result in enumerate(results, 1):
        score = result.get("qualification", {}).get("score", 0)
        fit_level = result.get("qualification", {}).get("fit_level", "unknown")
        status = result.get("outreach", {}).get("status", "not_sent")
        
        emoji = "🟢" if score > 0.6 else "🟡" if score > 0.4 else "🔴"
        print(f"{emoji} Prospect #{i}: Score {score:.2f} ({fit_level}) - Outreach: {status}")


def interactive_chat_demo():
    """Demo interactive chat with agent."""
    from app.sdr_agent import SDRAgent
    
    print("\n" + "="*60)
    print("💬 SDR Agent - Interactive Chat Demo")
    print("="*60)
    print("\nYou can ask the agent to:")
    print("- Research a company")
    print("- Draft outreach messages")
    print("- Suggest lead sources")
    print("- Qualify prospects")
    print("\nType 'quit' to exit\n")
    
    agent = SDRAgent()
    
    # Example prompts
    examples = [
        "How would you qualify a VP of Sales at a 200-person SaaS company?",
        "Draft a LinkedIn message for a Director of Marketing at a tech startup",
        "What are the best ways to find leads in the fintech industry?"
    ]
    
    print("Example questions you can ask:")
    for i, ex in enumerate(examples, 1):
        print(f"  {i}. {ex}")
    
    print()
    
    while True:
        try:
            message = input("You: ").strip()
            
            if not message:
                continue
            
            if message.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! 👋\n")
                break
            
            response = agent.chat(message)
            print(f"\nAgent: {response}\n")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋\n")
            break


def main():
    """Run complete demo."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SDR Agent Demo")
    parser.add_argument("--skip-import", action="store_true", help="Skip lead import")
    parser.add_argument("--channel", default="email", choices=["email", "linkedin"])
    parser.add_argument("--chat", action="store_true", help="Run interactive chat demo")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run (don't actually send)")
    
    args = parser.parse_args()
    
    # Setup
    setup_database()
    
    if args.chat:
        interactive_chat_demo()
        return
    
    # Import leads
    if not args.skip_import:
        prospect_ids = import_leads()
    else:
        # Use existing prospects
        from app.crm import ProspectManager
        prospects = ProspectManager.list_prospects(limit=10)
        prospect_ids = [p["id"] for p in prospects]
        
        if not prospect_ids:
            print("❌ No prospects found. Run without --skip-import first.")
            return
        
        print(f"✅ Using {len(prospect_ids)} existing prospects")
    
    # Run workflow
    results = run_sdr_workflow(prospect_ids, channel=args.channel, dry_run=args.dry_run)
    
    # Show summary
    show_summary(results)
    
    print("\n" + "="*60)
    print("✅ Demo Complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Check prospects in database: python -m app.crm")
    print("2. Run interactive chat: python examples/sdr_workflow.py --chat")
    print("3. Import your own leads: python -m app.lead_finder import-csv leads.csv")
    print("4. Customize ICP criteria in app/sdr_agent.py")
    print()


if __name__ == "__main__":
    main()
