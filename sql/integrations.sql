-- Integration Schema: OAuth tokens, CRM sync, campaigns, and Typeform ingestion
-- Run this after prospects.sql to add integration tables

-- OAuth Tokens Table
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,  -- User identifier
    provider VARCHAR(50) NOT NULL,  -- 'typeform', 'hubspot', 'salesforce', 'google_calendar', 'outlook_calendar'
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    scope TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

CREATE INDEX idx_oauth_tokens_user ON oauth_tokens(user_id);
CREATE INDEX idx_oauth_tokens_provider ON oauth_tokens(provider);
CREATE INDEX idx_oauth_tokens_expires_at ON oauth_tokens(expires_at);

-- CRM Sync Metadata Table
CREATE TABLE IF NOT EXISTS crm_sync_metadata (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,  -- 'hubspot', 'salesforce'
    external_id VARCHAR(255) NOT NULL,  -- CRM's ID for this prospect
    raw_data JSONB DEFAULT '{}',  -- Full CRM record for reference
    synced_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(prospect_id, provider)
);

CREATE INDEX idx_crm_sync_prospect ON crm_sync_metadata(prospect_id);
CREATE INDEX idx_crm_sync_provider ON crm_sync_metadata(provider);
CREATE INDEX idx_crm_sync_external_id ON crm_sync_metadata(external_id);

-- Typeform Ingestions Table
CREATE TABLE IF NOT EXISTS typeform_ingestions (
    id SERIAL PRIMARY KEY,
    form_id VARCHAR(255) UNIQUE NOT NULL,
    form_title TEXT,
    response_count INTEGER DEFAULT 0,
    chunks_count INTEGER DEFAULT 0,
    chunks_path TEXT,
    ingested_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_typeform_form_id ON typeform_ingestions(form_id);

-- Campaigns Table
CREATE TABLE IF NOT EXISTS campaigns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    trigger_type VARCHAR(50) NOT NULL,  -- 'manual', 'scheduled', 'event', 'webhook'
    trigger_config JSONB DEFAULT '{}',
    crm_source VARCHAR(50) NOT NULL,  -- 'hubspot', 'salesforce'
    crm_filters JSONB DEFAULT '{}',  -- Filters for fetching contacts
    max_prospects INTEGER DEFAULT 100,
    agent_config JSONB DEFAULT '{}',  -- Agent behavior config
    status VARCHAR(50) DEFAULT 'draft',  -- 'draft', 'active', 'paused', 'completed'
    last_triggered_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_trigger_type ON campaigns(trigger_type);
CREATE INDEX idx_campaigns_crm_source ON campaigns(crm_source);

-- Campaign Executions Table (audit log)
CREATE TABLE IF NOT EXISTS campaign_executions (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    triggered_by VARCHAR(255) NOT NULL,  -- user_id, 'system', 'webhook'
    prospects_imported INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    executed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_campaign_executions_campaign ON campaign_executions(campaign_id);
CREATE INDEX idx_campaign_executions_executed_at ON campaign_executions(executed_at);

-- Campaign Queue Table
CREATE TABLE IF NOT EXISTS campaign_queue (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'processed', 'failed'
    added_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    UNIQUE(campaign_id, prospect_id)
);

CREATE INDEX idx_campaign_queue_campaign ON campaign_queue(campaign_id);
CREATE INDEX idx_campaign_queue_prospect ON campaign_queue(prospect_id);
CREATE INDEX idx_campaign_queue_status ON campaign_queue(status);
CREATE INDEX idx_campaign_queue_pending ON campaign_queue(campaign_id, status) WHERE status = 'pending';

-- Add external_id to prospects table if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'prospects' AND column_name = 'external_id'
    ) THEN
        ALTER TABLE prospects ADD COLUMN external_id VARCHAR(255);
        CREATE INDEX idx_prospects_external_id ON prospects(external_id);
    END IF;
END $$;

-- Webhooks Table (for event-triggered campaigns)
CREATE TABLE IF NOT EXISTS webhooks (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,  -- 'hubspot', 'salesforce', 'typeform'
    event_type VARCHAR(100) NOT NULL,  -- 'contact.created', 'lead.updated', etc.
    campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL,
    webhook_url TEXT NOT NULL,
    secret_key TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_webhooks_provider ON webhooks(provider);
CREATE INDEX idx_webhooks_active ON webhooks(is_active);

-- Webhook Events Log
CREATE TABLE IF NOT EXISTS webhook_events (
    id SERIAL PRIMARY KEY,
    webhook_id INTEGER REFERENCES webhooks(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT false,
    error_message TEXT,
    received_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);

CREATE INDEX idx_webhook_events_webhook ON webhook_events(webhook_id);
CREATE INDEX idx_webhook_events_processed ON webhook_events(processed);

-- Document Uploads Table (for admin UI)
CREATE TABLE IF NOT EXISTS document_uploads (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    storage_path TEXT NOT NULL,
    chunks_path TEXT,
    chunks_count INTEGER DEFAULT 0,
    uploaded_by VARCHAR(255),  -- user_id or email
    ingested BOOLEAN DEFAULT false,
    ingested_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_document_uploads_uploaded_by ON document_uploads(uploaded_by);
CREATE INDEX idx_document_uploads_ingested ON document_uploads(ingested);

-- Integration Settings Table (for storing API keys, configs)
CREATE TABLE IF NOT EXISTS integration_settings (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) UNIQUE NOT NULL,
    is_enabled BOOLEAN DEFAULT false,
    config JSONB DEFAULT '{}',  -- Provider-specific config
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_integration_settings_provider ON integration_settings(provider);

-- Calendar Events Table (tracks booked meetings)
CREATE TABLE IF NOT EXISTS calendar_events (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,  -- User who owns the calendar
    provider VARCHAR(50) NOT NULL,  -- 'google', 'outlook'
    event_id VARCHAR(255) NOT NULL,  -- Provider's event ID
    title VARCHAR(255) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    attendees JSONB DEFAULT '[]',  -- Array of attendee emails
    location TEXT,
    description TEXT,
    conferencing_link TEXT,
    status VARCHAR(50) DEFAULT 'confirmed',  -- 'confirmed', 'cancelled', 'tentative'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, provider, event_id)
);

CREATE INDEX idx_calendar_events_user ON calendar_events(user_id);
CREATE INDEX idx_calendar_events_provider ON calendar_events(provider);
CREATE INDEX idx_calendar_events_start_time ON calendar_events(start_time);
CREATE INDEX idx_calendar_events_status ON calendar_events(status);

-- Insert default integration settings
INSERT INTO integration_settings (provider, is_enabled, config) VALUES
    ('typeform', false, '{"auto_ingest": true}'),
    ('hubspot', false, '{"auto_sync": false, "sync_interval": "1 hour"}'),
    ('salesforce', false, '{"auto_sync": false, "sync_interval": "1 hour"}'),
    ('google_calendar', false, '{"default_duration": 30, "buffer_minutes": 15}'),
    ('outlook_calendar', false, '{"default_duration": 30, "buffer_minutes": 15}')
ON CONFLICT (provider) DO NOTHING;

-- Comments for documentation
COMMENT ON TABLE oauth_tokens IS 'OAuth 2.0 tokens for CRM, calendar, and form integrations';
COMMENT ON TABLE crm_sync_metadata IS 'Tracks synced prospects from external CRMs';
COMMENT ON TABLE typeform_ingestions IS 'Tracks Typeform form response ingestions';
COMMENT ON TABLE campaigns IS 'Campaign definitions with trigger configs';
COMMENT ON TABLE campaign_executions IS 'Audit log of campaign trigger executions';
COMMENT ON TABLE campaign_queue IS 'Queue of prospects to process in campaigns';
COMMENT ON TABLE webhooks IS 'Webhook configurations for event-driven campaigns';
COMMENT ON TABLE webhook_events IS 'Log of received webhook events';
COMMENT ON TABLE document_uploads IS 'Tracks manually uploaded documents';
COMMENT ON TABLE integration_settings IS 'Global integration enable/disable and configs';
COMMENT ON TABLE calendar_events IS 'Tracks meetings booked via Google/Outlook Calendar integrations';
