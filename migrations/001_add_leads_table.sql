-- ============================================
-- Migration: Add leads table
-- Run this in Supabase SQL Editor
-- ============================================

CREATE TABLE IF NOT EXISTS leads (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    analyzed_post_id UUID NOT NULL REFERENCES analyzed_posts(id) ON DELETE CASCADE,
    raw_post_id UUID NOT NULL REFERENCES raw_posts(id) ON DELETE CASCADE,
    confidence FLOAT NOT NULL,
    reason TEXT,
    suggested_service TEXT,
    sentiment_score FLOAT,
    platform TEXT,
    author TEXT,
    post_title TEXT,
    post_content TEXT,
    post_url TEXT,
    status TEXT DEFAULT 'new',  -- 'new', 'contacted', 'replied', 'converted', 'skipped'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(analyzed_post_id)
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_confidence ON leads(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);

CREATE TRIGGER trg_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
