-- ============================================
-- AI-Powered Social Listening & Outreach System
-- Supabase Schema
-- ============================================

-- Updated-at trigger function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 1. Raw Posts
-- ============================================
CREATE TABLE IF NOT EXISTS raw_posts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    author TEXT,
    title TEXT,
    content TEXT NOT NULL,
    url TEXT,
    subreddit TEXT,
    score INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(platform, post_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_posts_platform ON raw_posts(platform);
CREATE INDEX IF NOT EXISTS idx_raw_posts_collected_at ON raw_posts(collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_posts_subreddit ON raw_posts(subreddit);

DROP TRIGGER IF EXISTS trg_raw_posts_updated_at ON raw_posts;
CREATE TRIGGER trg_raw_posts_updated_at
    BEFORE UPDATE ON raw_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 2. Analyzed Posts
-- ============================================
CREATE TABLE IF NOT EXISTS analyzed_posts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    raw_post_id UUID NOT NULL REFERENCES raw_posts(id) ON DELETE CASCADE,
    is_frustrated BOOLEAN NOT NULL DEFAULT FALSE,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    reason TEXT,
    suggested_service TEXT,
    sentiment_score FLOAT,
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(raw_post_id)
);

CREATE INDEX IF NOT EXISTS idx_analyzed_frustrated ON analyzed_posts(is_frustrated, confidence DESC);
CREATE INDEX IF NOT EXISTS idx_analyzed_at ON analyzed_posts(analyzed_at DESC);

DROP TRIGGER IF EXISTS trg_analyzed_posts_updated_at ON analyzed_posts;
CREATE TRIGGER trg_analyzed_posts_updated_at
    BEFORE UPDATE ON analyzed_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 3. Leads (qualified frustrated posts)
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

DROP TRIGGER IF EXISTS trg_leads_updated_at ON leads;
CREATE TRIGGER trg_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 4. Outreach
-- ============================================
CREATE TABLE IF NOT EXISTS outreach (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    analyzed_post_id UUID NOT NULL REFERENCES analyzed_posts(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,  -- 'linkedin', 'twitter', 'email'
    message_sent TEXT,
    response_received TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending', 'sent', 'replied', 'failed'
    sent_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach(status);
CREATE INDEX IF NOT EXISTS idx_outreach_sent_at ON outreach(sent_at DESC);

DROP TRIGGER IF EXISTS trg_outreach_updated_at ON outreach;
CREATE TRIGGER trg_outreach_updated_at
    BEFORE UPDATE ON outreach
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 4. Settings (key-value config store)
-- ============================================
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_settings_updated_at ON settings;
CREATE TRIGGER trg_settings_updated_at
    BEFORE UPDATE ON settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Seed default settings
INSERT INTO settings (key, value) VALUES
    ('subreddits', 'freelance,webdev,forhire,smallbusiness,startups'),
    ('services', 'web development,automation,design,consulting'),
    ('confidence_threshold', '0.8'),
    ('llm_model', 'gpt-4o-mini'),
    ('poll_interval_minutes', '10'),
    ('sentiment_threshold', '-0.05'),
    ('frustration_keywords', 'frustrated,stuck,can''t figure out,need help with,struggling,impossible,giving up,so hard,anyone know how,desperate')
ON CONFLICT (key) DO NOTHING;
