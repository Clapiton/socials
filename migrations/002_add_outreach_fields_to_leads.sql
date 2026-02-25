-- ============================================
-- Migration: Add outreach fields to leads table
-- Run this in Supabase SQL Editor
-- ============================================

ALTER TABLE IF EXISTS leads 
ADD COLUMN IF NOT EXISTS outreach_subject TEXT,
ADD COLUMN IF NOT EXISTS outreach_body TEXT,
ADD COLUMN IF NOT EXISTS contact_email TEXT;
