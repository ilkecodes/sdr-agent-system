#!/usr/bin/env python3
"""Example: Complete CRM integration workflow.

Demonstrates:
- HubSpot OAuth and contact import
- Salesforce OAuth and lead import
- Typeform form ingestion
- Campaign creation and triggering
- Knowledge base-powered briefings
"""

import os
from dotenv import load_dotenv

load_dotenv()

def example_hubspot_integration():
    """Example: HubSpot integration workflow."""
    print("\n" + "="*60)
    print("📊 HubSpot Integration Example")
    print("="*60 + "\n")
    
    from app.hubspot_integration import (
        authenticate_hubspot,
        import_hubspot_contact,
        generate_prospect_briefing,
        sync_interaction_to_hubspot
    )
    from app.crm import InteractionManager
    
    # Step 1: OAuth (done via Admin UI in production)
    print("1. OAuth Authentication:")
    print("   Visit Admin UI: http://localhost:8000")
    print("   Click 'Connect' next to HubSpot")
    print("   Or get auth URL programmatically:")
    auth_url = authenticate_hubspot()
    print(f"   {auth_url}")
    
    # Step 2: Import contact
    print("\n2. Import Contact:")
    try:
        # Replace with real HubSpot contact ID
        contact_id = os.getenv("EXAMPLE_HUBSPOT_CONTACT_ID", "12345")
        prospect_id = import_hubspot_contact(contact_id)
        print(f"   ✅ Imported contact as prospect ID: {prospect_id}")
        
        # Step 3: Generate briefing
        print("\n3. Generate Pre-Call Briefing:")
        briefing = generate_prospect_briefing(prospect_id)
        print(f"   {briefing}")
        
        # Step 4: Log interaction locally
        print("\n4. Log Interaction:")
        interaction_id = InteractionManager.log_interaction(
            prospect_id=prospect_id,
            type="call",
            content="Discussed product features and pricing",
            channel="phone",
            direction="outbound",
            subject="Product Demo Call"
        )
        print(f"   ✅ Logged interaction ID: {interaction_id}")
        
        # Step 5: Sync back to HubSpot
        print("\n5. Sync to HubSpot:")
        result = sync_interaction_to_hubspot(prospect_id, interaction_id)
        print(f"   ✅ Created HubSpot call activity: {result.get('id')}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print("   Make sure to complete OAuth first via Admin UI")


def example_salesforce_integration():
    """Example: Salesforce integration workflow."""
    print("\n" + "="*60)
    print("☁️  Salesforce Integration Example")
    print("="*60 + "\n")
    
    from app.salesforce_integration import (
        authenticate_salesforce,
        import_salesforce_lead,
        import_campaign_members,
        sync_interaction_to_salesforce
    )
    
    # Step 1: OAuth
    print("1. OAuth Authentication:")
    print("   Visit Admin UI: http://localhost:8000")
    print("   Click 'Connect' next to Salesforce")
    print("   Or get auth URL:")
    auth_url = authenticate_salesforce()
    print(f"   {auth_url}")
    
    # Step 2: Import from campaign
    print("\n2. Import Campaign Members:")
    try:
        campaign_id = os.getenv("EXAMPLE_SALESFORCE_CAMPAIGN_ID", "701...")
        prospect_ids = import_campaign_members(campaign_id, limit=10)
        print(f"   ✅ Imported {len(prospect_ids)} prospects")
        print(f"   Prospect IDs: {prospect_ids[:5]}...")
        
        if prospect_ids:
            # Step 3: Sync interaction
            print("\n3. Sync Interaction to Salesforce:")
            # (assuming interaction already logged)
            interaction_id = 1  # Replace with real ID
            result = sync_interaction_to_salesforce(prospect_ids[0], interaction_id)
            print(f"   ✅ Created Salesforce task: {result.get('id')}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print("   Make sure to complete OAuth first via Admin UI")


def example_typeform_integration():
    """Example: Typeform integration workflow."""
    print("\n" + "="*60)
    print("📝 Typeform Integration Example")
    print("="*60 + "\n")
    
    from app.typeform_integration import (
        authenticate_typeform,
        list_typeform_forms,
        ingest_typeform
    )
    
    # Step 1: OAuth
    print("1. OAuth Authentication:")
    print("   Visit Admin UI: http://localhost:8000")
    print("   Click 'Connect' next to Typeform")
    
    try:
        # Step 2: List forms
        print("\n2. List Forms:")
        forms = list_typeform_forms()
        print(f"   ✅ Found {len(forms)} forms")
        for form in forms[:3]:
            print(f"   - {form.get('title')} (ID: {form.get('id')})")
        
        if forms:
            # Step 3: Ingest responses
            print("\n3. Ingest Form Responses:")
            form_id = forms[0].get('id')
            result = ingest_typeform(form_id)
            print(f"   ✅ Ingested {result['responses_count']} responses")
            print(f"   ✅ Created {result['chunks_count']} chunks")
            print(f"   ✅ Added {result['chunks_ingested']} chunks to KB")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print("   Make sure to complete OAuth first via Admin UI")


def example_campaign_workflow():
    """Example: Campaign creation and triggering."""
    print("\n" + "="*60)
    print("🎯 Campaign Workflow Example")
    print("="*60 + "\n")
    
    from app.campaign_manager import (
        create_campaign,
        trigger_campaign,
        get_campaign_stats,
        CampaignManager
    )
    
    # Step 1: Create campaign
    print("1. Create Campaign:")
    campaign_id = create_campaign(
        name="Q1 2025 Outreach",
        description="Target new leads from HubSpot",
        trigger_type="manual",
        crm_source="hubspot",
        crm_filters={"lifecyclestage": "lead"},
        max_prospects=50
    )
    print(f"   ✅ Created campaign ID: {campaign_id}")
    
    # Step 2: Activate campaign
    print("\n2. Activate Campaign:")
    CampaignManager.activate_campaign(campaign_id)
    print(f"   ✅ Campaign activated")
    
    # Step 3: Trigger campaign
    print("\n3. Trigger Campaign:")
    try:
        result = trigger_campaign(campaign_id, triggered_by="example_script")
        print(f"   ✅ Imported {result['prospects_imported']} prospects")
        print(f"   Prospect IDs: {result['prospect_ids'][:5]}...")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print("   Make sure CRM is connected first")
    
    # Step 4: Check stats
    print("\n4. Campaign Stats:")
    stats = get_campaign_stats(campaign_id)
    print(f"   Total: {stats.get('total', 0)}")
    print(f"   Pending: {stats.get('pending', 0)}")
    print(f"   Processed: {stats.get('processed', 0)}")
    print(f"   Failed: {stats.get('failed', 0)}")


def example_knowledge_base_powered_briefing():
    """Example: KB-powered prospect briefing."""
    print("\n" + "="*60)
    print("🧠 Knowledge Base-Powered Briefing Example")
    print("="*60 + "\n")
    
    from app.hubspot_integration import generate_prospect_briefing
    from app.tools import KnowledgeBaseTools
    from app.crm import ProspectManager
    
    # Create sample prospect
    print("1. Create Sample Prospect:")
    prospect_id = ProspectManager.create_prospect(
        email="john@acmecorp.com",
        first_name="John",
        last_name="Doe",
        company_name="Acme Corp",
        job_title="VP of Sales",
        source="hubspot"
    )
    print(f"   ✅ Created prospect ID: {prospect_id}")
    
    # Search KB for relevant context
    print("\n2. Search Knowledge Base:")
    kb_results = KnowledgeBaseTools.search_knowledge(
        query="Acme Corp sales automation",
        top_k=3
    )
    
    if kb_results and not kb_results[0].get("error"):
        print(f"   ✅ Found {len(kb_results)} relevant chunks:")
        for i, chunk in enumerate(kb_results, 1):
            preview = chunk.get('content', '')[:100]
            score = chunk.get('relevance_score', 0)
            print(f"   {i}. Score: {score:.2f} - {preview}...")
    else:
        print("   ℹ️  No KB results (knowledge base may be empty)")
    
    # Generate briefing
    print("\n3. Generate Briefing:")
    briefing = generate_prospect_briefing(prospect_id)
    print(briefing)


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("🚀 CRM Integration Examples")
    print("="*60)
    print("\nThese examples demonstrate all integration capabilities.")
    print("Make sure to:")
    print("  1. Start Admin UI: python app/admin_ui.py")
    print("  2. Complete OAuth flows via http://localhost:8000")
    print("  3. Run database migrations: psql $DATABASE_URL -f sql/integrations.sql")
    print("\n" + "="*60)
    
    # Run examples
    example_hubspot_integration()
    example_salesforce_integration()
    example_typeform_integration()
    example_campaign_workflow()
    example_knowledge_base_powered_briefing()
    
    print("\n" + "="*60)
    print("✅ All Examples Complete!")
    print("="*60)
    print("\nNext steps:")
    print("  - Visit http://localhost:8000 to use the Admin UI")
    print("  - Check docs/CRM_INTEGRATIONS.md for full documentation")
    print("  - Create your own campaigns via the UI or API")
    print("\n")


if __name__ == "__main__":
    main()
