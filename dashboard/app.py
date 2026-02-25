"""
Flask dashboard — API + web interface for monitoring the social listening system.
"""

import logging
import threading
from flask import Flask, render_template, jsonify, request
import db
from task_manager import task_manager

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ─── Pages ──────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template("index.html")

    # ─── API: Stats ─────────────────────────────────────
    @app.route("/api/stats")
    def api_stats():
        try:
            stats = db.get_stats()
            return jsonify(stats)
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Posts ─────────────────────────────────────
    @app.route("/api/posts")
    def api_posts():
        try:
            limit = request.args.get("limit", 50, type=int)
            offset = request.args.get("offset", 0, type=int)
            platform = request.args.get("platform", None)
            posts = db.get_raw_posts(limit=limit, offset=offset, platform=platform)
            return jsonify(posts)
        except Exception as e:
            logger.error(f"Error fetching posts: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Leads ────────────────────────────────────
    @app.route("/api/leads")
    def api_leads():
        try:
            limit = request.args.get("limit", 50, type=int)
            offset = request.args.get("offset", 0, type=int)
            leads = db.get_leads(limit=limit, offset=offset)
            return jsonify(leads)
        except Exception as e:
            logger.error(f"Error fetching leads: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Outreach ─────────────────────────────────
    @app.route("/api/outreach")
    def api_outreach():
        try:
            limit = request.args.get("limit", 50, type=int)
            offset = request.args.get("offset", 0, type=int)
            outreach = db.get_outreach(limit=limit, offset=offset)
            return jsonify(outreach)
        except Exception as e:
            logger.error(f"Error fetching outreach: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Settings ─────────────────────────────────
    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        try:
            settings = db.get_settings()
            return jsonify(settings)
        except Exception as e:
            logger.error(f"Error fetching settings: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/settings", methods=["PUT"])
    def api_update_settings():
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400

            for key, value in data.items():
                db.update_setting(key, str(value))

            return jsonify({"status": "ok", "updated": list(data.keys())})
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Trigger Collect (selected platforms) ──────
    @app.route("/api/collect", methods=["POST"])
    def api_collect():
        try:
            data = request.get_json() or {}
            # Accept a list of sources; default to all if none specified
            all_sources = ["reddit", "hackernews", "mastodon", "devto", "apify"]
            sources = data.get("sources", all_sources)

            def run():
                try:
                    settings = db.get_settings()
                    keywords_raw = settings.get("frustration_keywords", "")
                    keywords = [kw.strip() for kw in keywords_raw.split(",") if kw.strip()]
                    subreddits_raw = settings.get("subreddits", "")
                    subreddits = [s.strip() for s in subreddits_raw.split(",") if s.strip()]

                    all_stats = []
                    step = 0
                    total = len(sources)

                    # Reddit (PRAW)
                    if "reddit" in sources:
                        step += 1
                        try:
                            task_manager.update_progress("collect", step, "Polling Reddit...")
                            from collectors.reddit_collector import collect_posts, is_configured
                            if is_configured():
                                stats = collect_posts()
                                all_stats.append({"platform": "reddit", "source": "praw", **stats})
                        except Exception as e:
                            logger.error(f"Reddit PRAW: {e}")

                    # Apify (Twitter, LinkedIn, Facebook, Instagram)
                    if "apify" in sources:
                        step += 1
                        try:
                            task_manager.update_progress("collect", step, "Running Apify scrapers...")
                            from collectors import apify_collector
                            results = apify_collector.collect_all(keywords, subreddits)
                            all_stats.extend(results)
                        except Exception as e:
                            logger.error(f"Apify: {e}")

                    # Hacker News
                    if "hackernews" in sources:
                        step += 1
                        try:
                            task_manager.update_progress("collect", step, "Checking Hacker News...")
                            from collectors import hackernews_collector
                            stats = hackernews_collector.collect_posts(keywords)
                            all_stats.append(stats)
                        except Exception as e:
                            logger.error(f"HN: {e}")

                    # Mastodon
                    if "mastodon" in sources:
                        step += 1
                        try:
                            task_manager.update_progress("collect", step, "Scraping Mastodon...")
                            from collectors import mastodon_collector
                            stats = mastodon_collector.collect_posts(keywords)
                            all_stats.append(stats)
                        except Exception as e:
                            logger.error(f"Mastodon: {e}")

                    # Dev.to
                    if "devto" in sources:
                        step += 1
                        try:
                            task_manager.update_progress("collect", step, "Fetching from Dev.to...")
                            from collectors import devto_collector
                            stats = devto_collector.collect_posts(keywords)
                            all_stats.append(stats)
                        except Exception as e:
                            logger.error(f"Dev.to: {e}")

                    task_manager.complete_task("collect", "Collection finished successfully", {"stats": all_stats})
                    logger.info(f"Background collect finished: {all_stats}")
                except Exception as e:
                    task_manager.fail_task("collect", str(e))
                    logger.error(f"Background collect error: {e}")

            task_manager.start_task("collect", total=len(sources), message=f"Collecting from {', '.join(sources)}...")
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            return jsonify({
                "status": "started",
                "message": f"Collection started for: {', '.join(sources)}",
            })
        except Exception as e:
            logger.error(f"Error starting collection: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Trigger Analyze ──────────────────────────
    @app.route("/api/analyze", methods=["POST"])
    def api_analyze():
        try:
            from analysis.pipeline import run_pipeline
            def run():
                try:
                    stats = run_pipeline()
                    task_manager.complete_task("analyze", "Analysis finished successfully", stats)
                    logger.info(f"Background analysis finished: {stats}")
                except Exception as e:
                    task_manager.fail_task("analyze", str(e))
                    logger.error(f"Background analysis error: {e}")

            task_manager.start_task("analyze", total=0, message="Preparing to analyze posts...")
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            return jsonify({"status": "started", "message": "Analysis started in background"})
        except Exception as e:
            logger.error(f"Error starting analysis: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Task Status ──────────────────────────────
    @app.route("/api/task-status")
    def api_task_status():
        task_type = request.args.get("type")
        return jsonify(task_manager.get_status(task_type))

    # ─── API: Manual Import ────────────────────────────
    @app.route("/api/import", methods=["POST"])
    def api_import():
        try:
            from collectors.manual_import import import_text, import_csv
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400

            import_type = data.get("type", "text")  # "text" or "csv"

            if import_type == "csv":
                csv_content = data.get("content", "")
                result = import_csv(csv_content)
            else:
                text = data.get("content", "")
                author = data.get("author", "manual")
                label = data.get("label", "")
                result = import_text(text, author=author, source_label=label)

            return jsonify(result)
        except Exception as e:
            logger.error(f"Error importing: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Get Single Lead ─────────────────────────
    @app.route("/api/leads/<lead_id>")
    def api_get_lead(lead_id):
        try:
            lead = db.get_lead_by_id(lead_id)
            if not lead:
                return jsonify({"error": "Lead not found"}), 404
            return jsonify(lead)
        except Exception as e:
            logger.error(f"Error fetching lead: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Generate Outreach Message ───────────────
    @app.route("/api/outreach/generate", methods=["POST"])
    def api_generate_outreach():
        try:
            data = request.get_json()
            if not data or "lead_id" not in data:
                return jsonify({"error": "lead_id required"}), 400

            lead = db.get_lead_by_id(data["lead_id"])
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            # Return the pre-generated message from Supabase (enriched by n8n)
            if lead.get("outreach_subject") and lead.get("outreach_body"):
                return jsonify({
                    "subject": lead["outreach_subject"],
                    "body": lead["outreach_body"],
                    "contact_info": lead.get("contact_email", "")
                })

            return jsonify({
                "status": "pending",
                "message": "Enrichment in progress. Please wait a few seconds for n8n to generate the draft."
            }), 202
            
        except Exception as e:
            logger.error(f"Error fetching outreach: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Log Outreach Result ─────────────────────
    @app.route("/api/outreach/log", methods=["POST"])
    def api_log_outreach():
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400

            from datetime import datetime, timezone
            outreach_data = {
                "analyzed_post_id": data["analyzed_post_id"],
                "channel": data.get("channel", "email"),
                "message_sent": data.get("message", ""),
                "status": data.get("status", "draft"),
                "sent_at": data.get("sent_at", datetime.now(timezone.utc).isoformat()),
            }
            result = db.insert_outreach(outreach_data)
            return jsonify(result or {"status": "ok"})
        except Exception as e:
            logger.error(f"Error logging outreach: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Send Outreach (Generate + Log) ──────────
    @app.route("/api/outreach/send", methods=["POST"])
    def api_send_outreach():
        """Log the n8n-generated draft to the outreach table."""
        try:
            from datetime import datetime, timezone
            data = request.get_json()
            if not data or "lead_id" not in data:
                return jsonify({"error": "lead_id required"}), 400

            lead = db.get_lead_by_id(data["lead_id"])
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            # Ensure we have the n8n-generated draft
            if not lead.get("outreach_subject") or not lead.get("outreach_body"):
                return jsonify({
                    "status": "pending",
                    "message": "Enrichment in progress. Cannot log draft until n8n finishes."
                }), 202

            # Log as draft
            outreach_data = {
                "analyzed_post_id": data["lead_id"],
                "channel": data.get("channel", "email"),
                "message_sent": f"Subject: {lead['outreach_subject']}\n\n{lead['outreach_body']}",
                "status": "draft",
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
            outreach_record = db.insert_outreach(outreach_data)

            return jsonify({
                "status": "draft_created",
                "message": {
                    "subject": lead["outreach_subject"],
                    "body": lead["outreach_body"]
                },
                "outreach": outreach_record,
            })
        except Exception as e:
            logger.error(f"Error logging outreach: {e}")
            return jsonify({"error": str(e)}), 500

    # ─── API: Webhook for n8n ─────────────────────────
    @app.route("/api/webhook/lead", methods=["POST"])
    def api_webhook_lead():
        """Receives lead notifications and can forward to n8n."""
        try:
            import os
            import requests as http_requests
            data = request.get_json()
            if not data or "lead_id" not in data:
                return jsonify({"error": "lead_id required"}), 400

            lead = db.get_lead_by_id(data["lead_id"])
            if not lead:
                return jsonify({"error": "Lead not found"}), 404

            # Forward to n8n webhook if configured
            n8n_url = db.get_setting("n8n_webhook_url", "")
            if n8n_url:
                try:
                    payload = {
                        "lead_id": data["lead_id"],
                        "confidence": lead.get("confidence", 0),
                        "reason": lead.get("reason", ""),
                        "suggested_service": lead.get("suggested_service", ""),
                        "raw_post": lead.get("raw_posts", {}),
                    }
                    http_requests.post(n8n_url, json=payload, timeout=10)
                    logger.info(f"Forwarded lead {data['lead_id']} to n8n")
                except Exception as e:
                    logger.error(f"Failed to forward to n8n: {e}")

            return jsonify({"status": "ok", "lead_id": data["lead_id"]})
        except Exception as e:
            logger.error(f"Error in webhook: {e}")
            return jsonify({"error": str(e)}), 500

    return app
