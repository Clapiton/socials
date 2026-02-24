## Project Brief: AI-Powered Social Listening & Outreach System

### 1. Project Overview
**Purpose**  
Build an automated system that monitors multiple social media platforms for posts where users express frustration about getting a job or task done. The system will identify high-quality leads, store them in Supabase, and trigger personalized outreach to offer the user’s services (e.g., freelancing, consulting). The goal is to generate job opportunities by proactively connecting with people who need help.

**Target Users**  
Freelancers, consultants, or small business owners offering services (e.g., web development, design, writing, marketing) who want to find clients by solving real-time problems expressed on social media.

### 2. Objectives
- Continuously monitor social platforms (Reddit, Twitter/X, etc.) for frustration-related posts.
- Use AI (LLMs) to accurately detect genuine frustration about completing a job/task.
- Store raw posts and analysis results in Supabase for querying and lead management.
- Automate personalized outreach via LinkedIn, Twitter DMs, or email when a high-quality lead is identified.
- Ensure compliance with platform terms of service and privacy regulations.
- Provide a dashboard (optional) to review leads and outreach history.

### 3. Key Features
#### 3.1 Data Collection
- **Multi‑Platform Support**  
  - Reddit: monitor specific subreddits or keywords via `praw` (official API).  
  - Twitter/X: use filtered stream API (v2) for real‑time keyword tracking.  
  - (Optional) Extend to other platforms (Mastodon, Facebook public groups) via APIs or third‑party tools like Bright Data.
- **Scheduled Polling & Real‑Time Streaming**  
  - Poll Reddit every 5–10 minutes.  
  - Stream Twitter continuously (if using streaming API).  
  - Use a timer trigger to ensure regular checks.

#### 3.2 AI‑Powered Frustration Detection
- **Keyword Pre‑Filter**  
  - Initial filter using a curated list of frustration indicators (e.g., "frustrated", "stuck", "can't figure out", "need help with", "this job", "task").
- **Sentiment Analysis**  
  - Apply VADER or TextBlob to gauge negative sentiment.
- **LLM‑Based Classification**  
  - For posts passing the pre‑filter, invoke an LLM (e.g., GPT‑4 via API) with a prompt to determine if the post expresses genuine frustration about getting a job/task done.  
  - LLM returns a structured JSON: `{ "is_frustrated": boolean, "confidence": float, "reason": string, "suggested_service": string }`.
- **Storage of Results**  
  - Save the original post and LLM output in Supabase for later analysis and lead scoring.

#### 3.3 Lead Storage & Management (Supabase)
- **Tables**  
  - `raw_posts`: id, platform, post_id, author, content, url, created_at, collected_at.  
  - `analyzed_posts`: id, raw_post_id, is_frustrated, confidence, reason, suggested_service, analyzed_at.  
  - `outreach`: id, analyzed_post_id, channel (linkedin/twitter/email), message_sent, response_received, sent_at.
- **Database Functions**  
  - Automatic timestamp triggers.  
  - Row‑level security (if multiple users/teams).
- **Real‑time Webhooks**  
  - Supabase can fire a webhook when a new row with `is_frustrated = true` and high confidence is inserted into `analyzed_posts`. This triggers the outreach workflow.

#### 3.4 Automated Outreach
- **Orchestration with Pipedream / n8n**  
  - Webhook from Supabase triggers a workflow.  
  - Workflow steps:  
    1. Fetch enriched data (optional): Use Proxycurl to find email/LinkedIn profile of the author.  
    2. Generate personalized message using an LLM (e.g., “Draft a helpful, non‑salesy message offering my services as a [profession] based on the user’s post.”).  
    3. Send message via appropriate channel:  
       - **LinkedIn**: Send connection request with note (if allowed) or InMail.  
       - **Twitter**: Send DM (if user allows) or public reply.  
       - **Email**: Send via Gmail/SendGrid if email is available.  
    4. Log the outreach attempt in Supabase.

#### 3.5 Dashboard (Optional)
- Simple web interface (e.g., Streamlit or Retool) connected to Supabase to view:
  - Recent frustrated posts.
  - Outreach status.
  - Performance metrics (e.g., response rate).

### 4. System Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Social Platforms│────▶│ Data Collection│────▶│   Supabase      │────▶│   Automation    │
│ (Twitter, Reddit)│     │ (Python workers)│     │  (Storage +     │     │  (Pipedream/n8n)│
└─────────────────┘     └──────────────┘     │   Webhooks)      │     └────────┬────────┘
                                              └─────────────────┘              │
                                                    │                          │
                                                    ▼                          ▼
                                              ┌─────────────────┐     ┌─────────────────┐
                                              │   LLM Service   │     │   Outreach      │
                                              │  (OpenAI, etc.) │     │   (LinkedIn,    │
                                              └─────────────────┘     │    Twitter, etc.)│
                                                                       └─────────────────┘
```

- **Data Collection Layer**: Python scripts using `tweepy`, `praw`, and possibly Bright Data scrapers, running as cron jobs or long‑running processes (e.g., on a small VM or as serverless functions).  
- **Storage Layer**: Supabase (PostgreSQL) with tables for raw posts, analysis, and outreach.  
- **AI Layer**: OpenAI API (or other LLM) called from serverless functions (Supabase Edge Functions or separate workers).  
- **Automation Layer**: Pipedream or n8n workflows triggered by Supabase webhooks, handling enrichment, message generation, and sending.  
- **Outreach Layer**: Social media APIs or email services.

### 5. Data Flow
1. **Collection**  
   - Twitter stream → new tweet → store in `raw_posts`.  
   - Reddit poll → new post → store in `raw_posts`.  
2. **Analysis**  
   - A scheduled job or database trigger processes unanalyzed raw posts.  
   - For each, call LLM to determine frustration.  
   - Store result in `analyzed_posts`.  
3. **Outreach Trigger**  
   - Supabase webhook on insert to `analyzed_posts` where `is_frustrated = true` and `confidence > 0.8`.  
   - Webhook payload sent to Pipedream/n8n endpoint.  
4. **Outreach Workflow**  
   - Enrich (optional).  
   - Generate message with LLM (using a prompt that includes the user's post).  
   - Send message and log in `outreach`.  
5. **Feedback Loop**  
   - If a user replies, manually update outreach record or build automated response handling.

### 6. Technology Stack
| Component              | Technology Choices                                                                 |
|------------------------|------------------------------------------------------------------------------------|
| **Data Collection**    | Python 3.10+, `tweepy`, `praw`, `requests`, Bright Data SDK (optional)            |
| **Scheduling**         | `cron` on VM / AWS Lambda / Google Cloud Scheduler                                 |
| **Storage**            | Supabase (PostgreSQL)                                                              |
| **AI / NLP**           | OpenAI API (GPT‑4 or GPT‑3.5), VADER for pre‑filter                               |
| **Automation**         | Pipedream / n8n (self‑hosted or cloud)                                            |
| **Outreach**           | LinkedIn API (via Pipedream app), Twitter API v2, Gmail/SendGrid                  |
| **Enrichment**         | Proxycurl API                                                                      |
| **Hosting**            | Data collectors: small EC2 instance / Railway / Heroku; Edge Functions: Supabase  |
| **Monitoring**         | Sentry for errors, Supabase logs, Pipedream logs                                   |

### 7. Implementation Phases
#### Phase 1: Foundation (2 weeks)
- Set up Supabase project with the required tables.
- Build a simple Reddit monitor that polls a few subreddits and stores raw posts.
- Integrate VADER sentiment as a basic filter.
- Test manual outreach for a few posts.

#### Phase 2: AI Integration (2 weeks)
- Integrate OpenAI API for frustration classification.
- Create a Supabase Edge Function that processes unanalyzed posts.
- Refine prompts and confidence thresholds.
- Build a simple dashboard (Streamlit) to view results.

#### Phase 3: Automation & Outreach (2 weeks)
- Set up Pipedream/n8n.
- Create webhook in Supabase.
- Build workflow: enrich (if possible), generate message, send via LinkedIn/Twitter.
- Implement logging back to Supabase.

#### Phase 4: Scaling & Polish (2 weeks)
- Add Twitter streaming.
- Handle rate limits and errors gracefully.
- Implement duplicate detection.
- Add more sophisticated lead scoring (e.g., based on post engagement).
- Monitor response rates and iterate on message personalization.

### 8. Success Metrics
- **Number of qualified leads** per day/week.
- **Conversion rate**: percentage of outreaches that result in a conversation or job.
- **Accuracy of frustration detection** (precision/recall on a test set).
- **Time from post to outreach** (aim for < 15 minutes).
- **Cost per lead** (API costs + compute).

### 9. Risks and Mitigations
| Risk                              | Mitigation                                                                 |
|-----------------------------------|----------------------------------------------------------------------------|
| Platform API changes/rate limits  | Use multiple tokens, implement exponential backoff, monitor API status.    |
| LLM cost scaling                  | Cache results for similar posts; use cheaper models (GPT‑3.5) for initial filter. |
| Outreach being seen as spam       | Ensure messages are helpful, not salesy; include opt‑out; respect platform rules. |
| Data privacy (GDPR)               | Anonymize where possible; store only necessary data; provide data deletion. |
| False positives in frustration    | Continuously refine prompts; add human review for borderline cases.        |
| IP bans from scraping             | Use official APIs primarily; if scraping, use rotating proxies/services.    |

### 10. Future Enhancements
- Add more platforms (Facebook groups, Discord servers via bots).
- Build a two‑way conversation system to handle replies automatically.
- Integrate with CRM (HubSpot) to track leads.
- Use vector embeddings to find semantically similar past successful leads.
- Offer a multi‑tenant SaaS version for other freelancers.

---

**Prepared by:** [Your Name/Team]  
**Date:** [Current Date]  
**Version:** 1.0