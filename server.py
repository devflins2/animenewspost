import os
import sys
import json
import threading
import time
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

# UTF-8 for console
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import Config
from storage import Storage
from anime_api import AnimeNewsAPI
from instagram_publisher import InstagramPublisher
from caption_generator import CaptionGenerator

storage = Storage()
api = AnimeNewsAPI()
publisher = InstagramPublisher()

# Scheduler state
scheduler_running = True
scheduler_thread = None
scheduler_state = {
    "last_post_time": None,
    "next_post_timestamp": None,
    "last_posted_title": None,
    "is_active": True
}

def background_scheduler():
    """Continuous background worker that auto-publishes anime news every interval on Render."""
    global scheduler_running, scheduler_state
    print("[Scheduler] 🚀 24/7 Automated Background Auto-Poster Started!")
    
    # Wait 5 seconds on startup before initial run to let server bind
    time.sleep(5)
    
    # Sync with live Instagram feed to prevent duplicate posts across server restarts
    try:
        storage.sync_with_instagram(publisher)
    except Exception as e:
        print(f"[Scheduler] Sync warning: {e}")
    
    interval_seconds = Config.POST_INTERVAL_MINUTES * 60

    while True:
        if scheduler_running:
            try:
                print("[Scheduler] Checking for unposted anime news...")
                posts = api.fetch_posts()
                unposted = []
                for p in posts:
                    if not storage.is_already_posted(p.get("id"), link=p.get("link"), title=p.get("title")):
                        unposted.append(p)

                if unposted:
                    next_p = unposted[-1]
                    print(f"[Scheduler] Auto-publishing: '{next_p.get('title')}'")
                    img_url = api.get_post_image_url(next_p)
                    caption = CaptionGenerator.generate(next_p)
                    res = publisher.publish_post(img_url, caption)
                    if res["success"]:
                        storage.record_post(next_p, res.get("media_id"))
                        print(f"[Scheduler] 🎉 Successfully published ID {next_p.get('id')} to Instagram!")
                        scheduler_state["last_post_time"] = datetime.now().isoformat()
                        scheduler_state["last_posted_title"] = next_p.get("title")
                        scheduler_state["next_post_timestamp"] = time.time() + interval_seconds
                    else:
                        print(f"[Scheduler] Failed to publish post: {res.get('error')}")
                else:
                    print("[Scheduler] All news items are already posted. Waiting for next cycle...")
                    # Set next check time to 2 minutes if no new unposted items
                    scheduler_state["next_post_timestamp"] = time.time() + 120
            except Exception as e:
                print(f"[Scheduler Exception] {e}")

        # Sleep interval (default 60 minutes or 2 mins if queue empty)
        sleep_dur = interval_seconds if scheduler_state.get("last_post_time") else 120
        time.sleep(sleep_dur)

class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP Request handler serving dashboard frontend and JSON REST API endpoints on Render."""

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/health", "/ping", "/api/health"]:
            self.send_json({"status": "healthy", "service": "anime-news-autopost", "time": datetime.now().isoformat()})
        elif path == "/api/status":
            self.send_json(self.get_status_data())
        elif path == "/api/posts":
            self.send_json(self.get_posts_data())
        elif path == "/api/history":
            self.send_json({"history": storage.get_recent_history(limit=50), "total": storage.get_posted_count()})
        else:
            # Serve static files (index.html, style.css, app.js)
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/publish-next":
            self.send_json(self.handle_publish_next())
        elif path == "/api/publish-specific":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            post_id = body.get("post_id")
            self.send_json(self.handle_publish_specific(post_id))
        else:
            self.send_response(404)
            self.end_headers()

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def get_status_data(self):
        acc = publisher.verify_account()
        return {
            "success": True,
            "account": {
                "id": acc.get("id"),
                "username": acc.get("username"),
                "account_type": acc.get("account_type"),
                "handle": Config.INSTAGRAM_HANDLE
            },
            "scheduler": {
                "is_running": scheduler_running,
                "last_post_time": scheduler_state["last_post_time"],
                "last_posted_title": scheduler_state["last_posted_title"],
                "next_post_timestamp": scheduler_state["next_post_timestamp"],
                "interval_minutes": Config.POST_INTERVAL_MINUTES
            },
            "stats": {
                "total_posted": storage.get_posted_count(),
                "interval_minutes": Config.POST_INTERVAL_MINUTES,
                "aspect_ratio": Config.IMAGE_ASPECT_RATIO,
                "api_url": Config.ANIME_API_URL
            }
        }

    def get_posts_data(self):
        posts = api.fetch_posts()
        enriched = []
        for p in posts:
            p_id = p.get("id")
            is_posted = storage.is_already_posted(p_id, link=p.get("link"), title=p.get("title"))
            img_url = api.get_post_image_url(p)
            caption = CaptionGenerator.generate(p)
            tags = CaptionGenerator.extract_dynamic_hashtags(p)
            enriched.append({
                **p,
                "is_posted": is_posted,
                "generated_image_url": img_url,
                "custom_caption": caption,
                "dynamic_hashtags": tags
            })
        return {"success": True, "count": len(enriched), "posts": enriched}

    def handle_publish_next(self):
        posts = api.fetch_posts()
        unposted = [p for p in posts if not storage.is_already_posted(p.get("id"), link=p.get("link"), title=p.get("title"))]
        if not unposted:
            return {"success": False, "error": "No unposted articles found in the feed!"}
        
        target = unposted[-1]
        img_url = api.get_post_image_url(target)
        caption = CaptionGenerator.generate(target)
        res = publisher.publish_post(img_url, caption)
        if res["success"]:
            storage.record_post(target, res.get("media_id"))
            return {"success": True, "post": target, "media_id": res.get("media_id"), "permalink": res.get("permalink")}
        return {"success": False, "error": res.get("error"), "step": res.get("step")}

    def handle_publish_specific(self, post_id):
        if not post_id:
            return {"success": False, "error": "Missing post_id"}
        posts = api.fetch_posts()
        target = next((p for p in posts if p.get("id") == post_id), None)
        if not target:
            return {"success": False, "error": f"Post with ID {post_id} not found in API"}
        
        img_url = api.get_post_image_url(target)
        caption = CaptionGenerator.generate(target)
        res = publisher.publish_post(img_url, caption)
        if res["success"]:
            storage.record_post(target, res.get("media_id"))
            return {"success": True, "post": target, "media_id": res.get("media_id"), "permalink": res.get("permalink")}
        return {"success": False, "error": res.get("error"), "step": res.get("step")}

def run_server(port=None):
    os.chdir(os.path.dirname(__file__))
    
    # Read PORT from Render environment variable or default to 5000
    if port is None:
        port = int(os.environ.get("PORT", 5000))
        
    host = "0.0.0.0"
    
    # Start 24/7 background scheduler thread
    global scheduler_thread
    scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
    scheduler_thread.start()

    server = HTTPServer((host, port), DashboardHandler)
    print(f"\n============================================================")
    print(f"  🎌 AniReport Studio Web Dashboard & Auto-Poster Active!")
    print(f"  🌐 Listening on http://{host}:{port}")
    print(f"  🚀 24/7 Hourly Background Scheduler Enabled")
    print(f"============================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down cleanly...")
        server.server_close()

if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_server(p)
