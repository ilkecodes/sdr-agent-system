"""Lead finder: discover and import prospects from various sources."""

from __future__ import annotations

import os
import csv
import json
from typing import List, Dict, Any, Optional
from app.crm import create_prospect, ProspectManager


class LeadFinder:
    """Tools for finding and importing leads."""
    
    @staticmethod
    def import_from_csv(
        csv_path: str,
        email_column: str = "email",
        mapping: Optional[Dict[str, str]] = None
    ) -> List[int]:
        """
        Import prospects from CSV file.
        
        Args:
            csv_path: Path to CSV file
            email_column: Name of email column
            mapping: Column name mapping, e.g. {"Email": "email", "Company": "company_name"}
        
        Returns:
            List of created prospect IDs
        """
        mapping = mapping or {}
        prospect_ids = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Map CSV columns to prospect fields
                prospect_data = {}
                
                for csv_col, value in row.items():
                    # Use mapping if provided, otherwise use column name as-is
                    field_name = mapping.get(csv_col, csv_col.lower().replace(" ", "_"))
                    prospect_data[field_name] = value
                
                # Ensure email is present
                email = prospect_data.get(email_column) or prospect_data.get("email")
                if not email:
                    continue
                
                try:
                    prospect_id = create_prospect(
                        email=email,
                        first_name=prospect_data.get("first_name"),
                        last_name=prospect_data.get("last_name"),
                        company_name=prospect_data.get("company_name"),
                        job_title=prospect_data.get("job_title"),
                        linkedin_url=prospect_data.get("linkedin_url"),
                        source="csv_import"
                    )
                    prospect_ids.append(prospect_id)
                    print(f"✅ Imported: {email}")
                except Exception as e:
                    print(f"❌ Failed to import {email}: {e}")
        
        return prospect_ids
    
    @staticmethod
    def search_linkedin(
        keywords: List[str],
        location: Optional[str] = None,
        company: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search LinkedIn for prospects (mock implementation).
        
        In production, use:
        - LinkedIn Sales Navigator API
        - Apollo.io API
        - Phantombuster automation
        """
        print(f"\n🔍 Searching LinkedIn:")
        print(f"  Keywords: {', '.join(keywords)}")
        if location:
            print(f"  Location: {location}")
        if company:
            print(f"  Company: {company}")
        
        # Mock results
        mock_results = [
            {
                "name": "John Doe",
                "title": "VP of Sales",
                "company": "Tech Corp",
                "linkedin_url": "https://linkedin.com/in/johndoe",
                "location": "San Francisco"
            },
            {
                "name": "Jane Smith",
                "title": "Director of Marketing",
                "company": "SaaS Inc",
                "linkedin_url": "https://linkedin.com/in/janesmith",
                "location": "New York"
            }
        ]
        
        print(f"  Found {len(mock_results)} profiles (mock data)")
        return mock_results
    
    @staticmethod
    def find_company_contacts(
        domain: str,
        roles: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find contacts at a specific company (mock implementation).
        
        In production, use:
        - Hunter.io API
        - Apollo.io API
        - Clearbit Prospector
        """
        roles = roles or ["VP", "Director", "Head of"]
        
        print(f"\n🏢 Finding contacts at: {domain}")
        print(f"  Target roles: {', '.join(roles)}")
        
        # Mock results
        mock_contacts = [
            {
                "email": f"vp.sales@{domain}",
                "first_name": "Michael",
                "last_name": "Johnson",
                "title": "VP of Sales",
                "linkedin_url": f"https://linkedin.com/in/michaeljohnson"
            }
        ]
        
        print(f"  Found {len(mock_contacts)} contacts (mock data)")
        return mock_contacts
    
    @staticmethod
    def enrich_prospect_list(prospect_ids: List[int]) -> Dict[str, int]:
        """
        Batch enrich a list of prospects.
        Returns stats on enrichment.
        """
        from app.sdr_agent import SDRAgent
        
        agent = SDRAgent()
        stats = {"enriched": 0, "failed": 0}
        
        print(f"\n🔄 Enriching {len(prospect_ids)} prospects...")
        
        for prospect_id in prospect_ids:
            try:
                agent.research_prospect(prospect_id)
                stats["enriched"] += 1
            except Exception as e:
                print(f"  ❌ Failed to enrich prospect {prospect_id}: {e}")
                stats["failed"] += 1
        
        print(f"\n✅ Enrichment complete: {stats['enriched']} succeeded, {stats['failed']} failed")
        return stats


def main():
    """CLI for lead finding tools."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Lead Finder CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Import CSV command
    import_parser = subparsers.add_parser("import-csv", help="Import prospects from CSV")
    import_parser.add_argument("csv_file", help="Path to CSV file")
    import_parser.add_argument("--email-col", default="email", help="Email column name")
    
    # Search LinkedIn command
    linkedin_parser = subparsers.add_parser("search-linkedin", help="Search LinkedIn")
    linkedin_parser.add_argument("keywords", nargs="+", help="Search keywords")
    linkedin_parser.add_argument("--location", help="Location filter")
    linkedin_parser.add_argument("--company", help="Company filter")
    
    # Find company contacts
    company_parser = subparsers.add_parser("find-contacts", help="Find contacts at company")
    company_parser.add_argument("domain", help="Company domain")
    company_parser.add_argument("--roles", nargs="+", help="Target roles")
    
    # Enrich command
    enrich_parser = subparsers.add_parser("enrich", help="Enrich prospect list")
    enrich_parser.add_argument("--stage", help="Filter by stage")
    enrich_parser.add_argument("--limit", type=int, default=50, help="Max prospects to enrich")
    
    args = parser.parse_args()
    
    finder = LeadFinder()
    
    if args.command == "import-csv":
        prospect_ids = finder.import_from_csv(args.csv_file, email_column=args.email_col)
        print(f"\n✅ Imported {len(prospect_ids)} prospects")
        
        # Ask if user wants to enrich
        if input("\nEnrich imported prospects? (y/n): ").lower() == 'y':
            finder.enrich_prospect_list(prospect_ids)
    
    elif args.command == "search-linkedin":
        results = finder.search_linkedin(
            keywords=args.keywords,
            location=args.location,
            company=args.company
        )
        
        # Display results
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['name']} - {result['title']} at {result['company']}")
            print(f"   {result['linkedin_url']}")
        
        # Ask to import
        if input("\nImport these prospects? (y/n): ").lower() == 'y':
            for result in results:
                # Try to extract email or use placeholder
                email = result.get("email", f"{result['name'].lower().replace(' ', '.')}@example.com")
                create_prospect(
                    email=email,
                    first_name=result.get("first_name") or result["name"].split()[0],
                    last_name=result.get("last_name") or result["name"].split()[-1],
                    company_name=result["company"],
                    job_title=result["title"],
                    linkedin_url=result["linkedin_url"],
                    source="linkedin_search"
                )
            print("✅ Prospects imported")
    
    elif args.command == "find-contacts":
        results = finder.find_company_contacts(args.domain, roles=args.roles)
        
        for result in results:
            create_prospect(
                email=result["email"],
                first_name=result["first_name"],
                last_name=result["last_name"],
                job_title=result["title"],
                company_domain=args.domain,
                linkedin_url=result.get("linkedin_url"),
                source="company_search"
            )
        
        print(f"✅ Imported {len(results)} contacts")
    
    elif args.command == "enrich":
        prospects = ProspectManager.list_prospects(stage=args.stage, limit=args.limit)
        prospect_ids = [p["id"] for p in prospects]
        
        if not prospect_ids:
            print("No prospects found to enrich")
            return
        
        finder.enrich_prospect_list(prospect_ids)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
