-- Prospect/Lead management schema for SDR agent system

-- Core prospect table
CREATE TABLE IF NOT EXISTS prospects (
  id SERIAL PRIMARY KEY,
  -- Basic info
  first_name TEXT,
  last_name TEXT,
  email TEXT UNIQUE,
  phone TEXT,
  linkedin_url TEXT,
  
  -- Company info
  company_name TEXT,
  company_domain TEXT,
  company_size TEXT,
  industry TEXT,
  job_title TEXT,
  seniority_level TEXT, -- C-level, VP, Director, Manager, IC
  
  -- Scoring & qualification
  lead_score FLOAT DEFAULT 0.0, -- 0-1 score
  stage TEXT DEFAULT 'new', -- new, researched, contacted, qualified, meeting, closed_won, closed_lost
  status TEXT DEFAULT 'active', -- active, bounced, opted_out, do_not_contact
  
  -- Enrichment data
  pain_points JSONB DEFAULT '[]'::jsonb,
  technologies JSONB DEFAULT '[]'::jsonb, -- tech stack they use
  social_profiles JSONB DEFAULT '{}'::jsonb,
  company_info JSONB DEFAULT '{}'::jsonb,
  
  -- Engagement tracking
  last_contacted_at TIMESTAMP,
  last_responded_at TIMESTAMP,
  next_followup_at TIMESTAMP,
  contact_attempts INT DEFAULT 0,
  
  -- Metadata
  source TEXT, -- manual, web_scrape, import, referral
  notes TEXT,
  assigned_to TEXT, -- agent or human owner
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- Interaction/activity log
CREATE TABLE IF NOT EXISTS interactions (
  id SERIAL PRIMARY KEY,
  prospect_id INT REFERENCES prospects(id) ON DELETE CASCADE,
  
  type TEXT NOT NULL, -- email_sent, email_received, linkedin_message, meeting_scheduled, note, call
  channel TEXT, -- email, linkedin, phone, in_person
  direction TEXT, -- outbound, inbound
  
  subject TEXT,
  content TEXT,
  metadata JSONB DEFAULT '{}'::jsonb, -- template_id, campaign_id, etc
  
  -- Status
  status TEXT, -- sent, delivered, opened, clicked, replied, bounced
  sentiment TEXT, -- positive, neutral, negative, objection
  
  -- Agent info
  agent_name TEXT, -- which agent handled this
  human_reviewed BOOLEAN DEFAULT false,
  
  created_at TIMESTAMP DEFAULT now()
);

-- Conversation threads (multi-turn dialogue state)
CREATE TABLE IF NOT EXISTS conversations (
  id SERIAL PRIMARY KEY,
  prospect_id INT REFERENCES prospects(id) ON DELETE CASCADE,
  
  -- Conversation state
  messages JSONB DEFAULT '[]'::jsonb, -- array of {role, content, timestamp}
  state TEXT DEFAULT 'active', -- active, paused, completed
  context JSONB DEFAULT '{}'::jsonb, -- discovered_pain_points, objections_raised, etc
  
  -- Workflow
  current_step TEXT, -- discovery, qualification, demo_request, pricing_discussion
  next_action TEXT, -- send_case_study, schedule_demo, send_pricing
  
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- Outreach campaigns (sequences/drips)
CREATE TABLE IF NOT EXISTS campaigns (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  
  -- Campaign config
  channel TEXT, -- email, linkedin, multi_channel
  template_sequence JSONB, -- [{step: 1, delay_days: 0, template_id: "..."}, ...]
  targeting_criteria JSONB, -- {industries: [...], titles: [...], company_size: [...]}
  
  -- Status
  status TEXT DEFAULT 'draft', -- draft, active, paused, completed
  
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- Templates for outreach
CREATE TABLE IF NOT EXISTS message_templates (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT, -- email, linkedin
  
  subject TEXT, -- for emails
  body TEXT,
  variables JSONB DEFAULT '[]'::jsonb, -- ["{first_name}", "{company_name}", "{pain_point}"]
  
  -- Performance tracking
  sent_count INT DEFAULT 0,
  opened_count INT DEFAULT 0,
  replied_count INT DEFAULT 0,
  
  created_at TIMESTAMP DEFAULT now()
);

-- Enrichment queue (async tasks for lead research)
CREATE TABLE IF NOT EXISTS enrichment_queue (
  id SERIAL PRIMARY KEY,
  prospect_id INT REFERENCES prospects(id) ON DELETE CASCADE,
  
  enrichment_type TEXT, -- linkedin_profile, company_info, tech_stack, news
  status TEXT DEFAULT 'pending', -- pending, in_progress, completed, failed
  
  result JSONB,
  error TEXT,
  
  created_at TIMESTAMP DEFAULT now(),
  completed_at TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_prospects_email ON prospects(email);
CREATE INDEX IF NOT EXISTS idx_prospects_company ON prospects(company_domain);
CREATE INDEX IF NOT EXISTS idx_prospects_stage ON prospects(stage);
CREATE INDEX IF NOT EXISTS idx_prospects_next_followup ON prospects(next_followup_at) WHERE next_followup_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_interactions_prospect ON interactions(prospect_id);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(type);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON interactions(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_prospect ON conversations(prospect_id);
CREATE INDEX IF NOT EXISTS idx_enrichment_status ON enrichment_queue(status) WHERE status = 'pending';

-- View: prospect summary with latest interaction
CREATE OR REPLACE VIEW prospect_summary AS
SELECT 
  p.*,
  i.latest_interaction,
  i.latest_interaction_type,
  c.conversation_id,
  c.current_step
FROM prospects p
LEFT JOIN LATERAL (
  SELECT created_at as latest_interaction, type as latest_interaction_type
  FROM interactions
  WHERE prospect_id = p.id
  ORDER BY created_at DESC
  LIMIT 1
) i ON true
LEFT JOIN LATERAL (
  SELECT id as conversation_id, current_step
  FROM conversations
  WHERE prospect_id = p.id AND state = 'active'
  ORDER BY updated_at DESC
  LIMIT 1
) c ON true;
