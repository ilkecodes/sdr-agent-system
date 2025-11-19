"""SDR Agent: autonomous agent for lead generation and outreach.

This agent can:
- Research prospects and companies
- Qualify leads against ICP
- Draft personalized outreach messages
- Send emails and LinkedIn messages
- Track interactions and follow-ups
"""

from __future__ import annotations

import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import ollama
from dotenv import load_dotenv

from app.crm import (
    ProspectManager, InteractionManager, ConversationManager,
    get_prospect, create_prospect, log_interaction
)
from app.tools import TOOL_REGISTRY, execute_tool, ResearchTools
from app import query as rag_query

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")


class SDRAgent:
    """Autonomous SDR agent with tool-calling capabilities."""
    
    def __init__(
        self,
        name: str = "SDR Agent",
        icp_criteria: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.icp_criteria = icp_criteria or self._default_icp()
        self.conversation_history = []
    
    @staticmethod
    def _default_icp() -> Dict[str, Any]:
        """Default Ideal Customer Profile."""
        return {
            "company_size": ["51-200", "201-500", "501-1000"],
            "industries": ["SaaS", "Technology", "Software"],
            "job_titles": ["VP", "Director", "Head of", "Chief"],
            "technologies": ["Salesforce", "HubSpot", "AWS"]
        }
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with tool descriptions."""
        tools_desc = "\n".join([
            f"- {name}: {func.__doc__ or 'No description'}"
            for name, func in TOOL_REGISTRY.items()
        ])
        
        return f"""You are an expert SDR (Sales Development Representative) agent.
Your goal is to help find, research, qualify, and engage potential customers.

🌟 PRIMARY RESOURCE: KNOWLEDGE BASE 🌟
ALWAYS search the knowledge base first before researching elsewhere.
The knowledge base contains:
- Product documentation and features
- Case studies and success stories
- Pricing and positioning information
- Company values and messaging
- Industry insights and use cases

Use 'search_knowledge' and 'answer_from_knowledge' tools to:
- Understand how our product helps prospects
- Find relevant case studies for similar companies
- Get accurate product/pricing information
- Craft personalized, value-focused messaging

Your Ideal Customer Profile (ICP):
{json.dumps(self.icp_criteria, indent=2)}

Available Tools:
{tools_desc}

When you need to use a tool, respond with a JSON object in this format:
{{
    "thought": "why I need this tool",
    "tool": "tool_name",
    "arguments": {{"arg1": "value1", "arg2": "value2"}}
}}

After using tools, provide your final answer in this format:
{{
    "thought": "summary of what I learned",
    "answer": "your response to the user",
    "next_steps": ["suggested action 1", "suggested action 2"]
}}

Workflow:
1. Search knowledge base for relevant product info
2. Research prospect (LinkedIn, company website, news)
3. Qualify against ICP using knowledge base insights
4. Draft personalized outreach citing specific product benefits from KB
5. Always cite sources from knowledge base for credibility

Always be professional, personalized, and value-focused in outreach.
Research before reaching out. Qualify leads against the ICP.
"""
    
    def _parse_llm_response(self, response: str) -> Tuple[Optional[str], Optional[Dict], Optional[str]]:
        """
        Parse LLM response for tool calls or final answers.
        Returns: (tool_name, arguments, answer)
        """
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            return None, None, response
        
        try:
            parsed = json.loads(json_match.group())
            
            # Check if it's a tool call
            if "tool" in parsed and "arguments" in parsed:
                return parsed["tool"], parsed["arguments"], None
            
            # Check if it's a final answer
            if "answer" in parsed:
                return None, None, parsed["answer"]
            
        except json.JSONDecodeError:
            pass
        
        return None, None, response
    
    def _call_llm(self, prompt: str, context: Optional[str] = None) -> str:
        """Call local LLM with system prompt and context."""
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        
        if context:
            messages.append({"role": "system", "content": f"Context:\n{context}"})
        
        # Add conversation history
        for msg in self.conversation_history[-5:]:  # Last 5 messages
            messages.append(msg)
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = ollama.chat(model=LLM_MODEL, messages=messages)
            return response['message']['content']
        except Exception as e:
            return f"Error calling LLM: {e}"
    
    def research_prospect(self, prospect_id: int) -> Dict[str, Any]:
        """Research a prospect and enrich their data."""
        prospect = get_prospect(prospect_id)
        if not prospect:
            return {"error": f"Prospect {prospect_id} not found"}
        
        print(f"\n🔍 Researching prospect: {prospect.get('email')}")
        
        enrichment = {}
        
        # Enrich from LinkedIn if URL provided
        if prospect.get("linkedin_url"):
            print("  - Enriching from LinkedIn profile...")
            tool_result = execute_tool("enrich_linkedin", linkedin_url=prospect["linkedin_url"])
            if tool_result.get("success"):
                enrichment.update(tool_result["result"])
        
        # Research company
        if prospect.get("company_domain"):
            print(f"  - Researching company: {prospect['company_domain']}")
            company_info = execute_tool("research_company", domain=prospect["company_domain"])
            if company_info.get("success"):
                enrichment["company_info"] = company_info["result"]
            
            # Find tech stack
            tech_stack = execute_tool("find_tech_stack", domain=prospect["company_domain"])
            if tech_stack.get("success"):
                enrichment["technologies"] = tech_stack["result"]
        
        # Update prospect with enriched data
        if enrichment:
            ProspectManager.update_prospect(prospect_id, **enrichment)
            print("  ✅ Enrichment complete")
        
        return enrichment
    
    def qualify_lead(self, prospect_id: int) -> Dict[str, Any]:
        """Qualify a lead against ICP and update score."""
        prospect = get_prospect(prospect_id)
        if not prospect:
            return {"error": f"Prospect {prospect_id} not found"}
        
        print(f"\n📊 Qualifying lead: {prospect.get('email')}")
        
        # Analyze fit
        fit_analysis = ResearchTools.analyze_prospect_fit(prospect, self.icp_criteria)
        
        score = fit_analysis["score"]
        fit_level = fit_analysis["fit_level"]
        
        print(f"  - Fit Score: {score:.2f} ({fit_level})")
        print(f"  - Reasons: {', '.join(fit_analysis['reasons']) if fit_analysis['reasons'] else 'No strong signals'}")
        
        # Update prospect score and stage
        ProspectManager.update_score(prospect_id, score)
        
        if score > 0.7:
            ProspectManager.update_stage(prospect_id, "qualified")
        elif score > 0.4:
            ProspectManager.update_stage(prospect_id, "researched")
        
        return fit_analysis
    
    def draft_outreach(
        self,
        prospect_id: int,
        channel: str = "email",
        context: Optional[str] = None
    ) -> Dict[str, str]:
        """Draft personalized outreach message using LLM + Knowledge Base."""
        prospect = get_prospect(prospect_id)
        if not prospect:
            return {"error": f"Prospect {prospect_id} not found"}
        
        print(f"\n✍️  Drafting {channel} outreach for: {prospect.get('email')}")
        
        # 🌟 SEARCH KNOWLEDGE BASE for relevant product info
        print("  📚 Searching knowledge base...")
        kb_query = f"product benefits for {prospect.get('industry')} {prospect.get('job_title')}"
        from app.tools import KnowledgeBaseTools
        
        try:
            kb_results = KnowledgeBaseTools.search_knowledge(kb_query, top_k=3)
            kb_context = "\n\n".join([
                f"[KB Source - Relevance {chunk.get('relevance_score', 0):.2f}]\n{chunk.get('content', '')[:400]}"
                for chunk in kb_results
                if 'error' not in chunk
            ])
            kb_count = len([c for c in kb_results if 'error' not in c])
            print(f"  ✅ Found {kb_count} relevant knowledge base sources")
        except Exception as e:
            print(f"  ⚠️  KB search failed: {e}")
            kb_context = ""
            kb_count = 0
        
        # Build context from prospect data
        prospect_context = f"""
Prospect Information:
- Name: {prospect.get('first_name')} {prospect.get('last_name')}
- Company: {prospect.get('company_name')}
- Title: {prospect.get('job_title')}
- Industry: {prospect.get('industry')}
- Company Size: {prospect.get('company_size')}
- Technologies: {', '.join(prospect.get('technologies') or [])}
- Lead Score: {prospect.get('lead_score', 0):.2f}

{context or ''}
"""
        
        # 🌟 Include knowledge base context in prompt
        kb_instructions = ""
        if kb_context:
            kb_instructions = f"""
CRITICAL: Use these sources from our knowledge base to personalize the message.
Reference specific product features, case studies, or benefits mentioned below.
DO NOT make up features - only use information from these sources.

Knowledge Base Context:
{kb_context}
"""
        else:
            kb_instructions = "Note: No specific knowledge base sources found. Use general value proposition."
        
        prompt = f"""Draft a personalized {channel} message for this prospect.

Requirements:
- Keep it short (3-4 sentences)
- Reference something specific about their company/role
- Cite specific product benefits from knowledge base sources
- Focus on value, not features
- Include a clear call-to-action
- Be conversational and human

Do NOT use placeholder text like [Company Name]. Use actual details from the prospect data.

{kb_instructions}

Prospect Data:
{prospect_context}

Respond with JSON: {{"subject": "...", "body": "...", "kb_sources_used": number}}
"""
        
        response = self._call_llm(prompt, context=prospect_context)
        
        # Parse response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                draft = json.loads(json_match.group())
                draft['kb_sources_available'] = kb_count
                print(f"  ✅ Draft complete (using {kb_count} KB sources)")
                return draft
            except json.JSONDecodeError:
                pass
        
        # Fallback: return raw response
        return {
            "subject": "Quick question", 
            "body": response,
            "kb_sources_available": kb_count
        }
    
    def send_outreach(
        self,
        prospect_id: int,
        message: Dict[str, str],
        channel: str = "email",
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Send outreach message and log interaction."""
        from app.tools import OutreachTools
        
        prospect = get_prospect(prospect_id)
        if not prospect:
            return {"error": f"Prospect {prospect_id} not found"}
        
        print(f"\n📤 Sending {channel} to: {prospect.get('email')}")
        
        # Send via appropriate channel
        if channel == "email":
            result = OutreachTools.send_email(
                to=prospect["email"],
                subject=message.get("subject", ""),
                body=message.get("body", ""),
                dry_run=dry_run
            )
        elif channel == "linkedin":
            result = OutreachTools.send_linkedin_message(
                profile_url=prospect.get("linkedin_url", ""),
                message=message.get("body", ""),
                dry_run=dry_run
            )
        else:
            return {"error": f"Unknown channel: {channel}"}
        
        # Log interaction
        if result.get("status") in ["sent", "dry_run"]:
            log_interaction(
                prospect_id=prospect_id,
                type=f"{channel}_sent",
                content=message.get("body", ""),
                channel=channel,
                direction="outbound",
                subject=message.get("subject"),
                agent_name=self.name
            )
            
            # Schedule follow-up
            OutreachTools.schedule_followup(prospect_id, days_from_now=3)
            
            print("  ✅ Outreach sent and logged")
        
        return result
    
    def run_full_workflow(
        self,
        prospect_id: int,
        channel: str = "email",
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Run complete SDR workflow:
        1. Research prospect
        2. Qualify lead
        3. Draft outreach
        4. Send message (if qualified)
        """
        print(f"\n{'='*60}")
        print(f"🤖 SDR Agent: Full Workflow for Prospect #{prospect_id}")
        print(f"{'='*60}")
        
        results = {}
        
        # Step 1: Research
        results["research"] = self.research_prospect(prospect_id)
        
        # Step 2: Qualify
        results["qualification"] = self.qualify_lead(prospect_id)
        
        # Step 3: Draft (if qualified)
        if results["qualification"]["score"] > 0.4:
            results["draft"] = self.draft_outreach(prospect_id, channel=channel)
            
            # Step 4: Send (if score is high enough)
            if results["qualification"]["score"] > 0.6:
                results["outreach"] = self.send_outreach(
                    prospect_id,
                    results["draft"],
                    channel=channel,
                    dry_run=dry_run
                )
            else:
                print("\n⏸️  Lead score too low - skipping outreach")
                results["outreach"] = {"status": "skipped", "reason": "low_score"}
        else:
            print("\n❌ Lead does not meet ICP criteria - workflow stopped")
            results["draft"] = {"status": "skipped", "reason": "not_qualified"}
            results["outreach"] = {"status": "skipped", "reason": "not_qualified"}
        
        print(f"\n{'='*60}")
        print("✅ Workflow Complete")
        print(f"{'='*60}\n")
        
        return results
    
    def chat(self, message: str, prospect_id: Optional[int] = None) -> str:
        """
        Interactive chat with agent.
        Agent can use tools and access prospect data.
        """
        context = ""
        if prospect_id:
            prospect = get_prospect(prospect_id)
            if prospect:
                context = f"Current Prospect: {json.dumps(prospect, indent=2, default=str)}"
        
        # Add message to history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Call LLM
        response = self._call_llm(message, context=context)
        
        # Parse for tool calls
        tool_name, arguments, answer = self._parse_llm_response(response)
        
        # Execute tool if requested
        if tool_name:
            print(f"\n🔧 Using tool: {tool_name}")
            tool_result = execute_tool(tool_name, **arguments)
            
            # Call LLM again with tool result
            tool_context = f"Tool Result:\n{json.dumps(tool_result, indent=2, default=str)}"
            follow_up = self._call_llm(
                "Based on the tool result, provide your final answer.",
                context=tool_context
            )
            
            _, _, answer = self._parse_llm_response(follow_up)
        
        # Add to history
        self.conversation_history.append({"role": "assistant", "content": answer or response})
        
        return answer or response


def main():
    """Demo/CLI for SDR agent."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SDR Agent CLI")
    parser.add_argument("--workflow", action="store_true", help="Run full workflow")
    parser.add_argument("--prospect-id", type=int, help="Prospect ID")
    parser.add_argument("--channel", default="email", choices=["email", "linkedin"])
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode")
    parser.add_argument("--chat", action="store_true", help="Interactive chat mode")
    
    args = parser.parse_args()
    
    agent = SDRAgent()
    
    if args.workflow:
        if not args.prospect_id:
            print("Error: --prospect-id required for workflow")
            return
        
        agent.run_full_workflow(
            prospect_id=args.prospect_id,
            channel=args.channel,
            dry_run=args.dry_run
        )
    
    elif args.chat:
        print("\n🤖 SDR Agent - Interactive Chat")
        print("Type 'quit' to exit\n")
        
        while True:
            try:
                message = input("You: ").strip()
                if message.lower() in ['quit', 'exit']:
                    break
                
                response = agent.chat(message, prospect_id=args.prospect_id)
                print(f"\nAgent: {response}\n")
            
            except KeyboardInterrupt:
                break
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
