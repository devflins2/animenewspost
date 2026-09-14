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
    """Continuous background worker that auto-publishes anime news with 100% duplicate protection & Game filter."""
    global scheduler_running, scheduler_state
    print("[Scheduler] 🚀 24/7 Automated Background Auto-Poster Active (Zero-Duplicate & Game Filter Shield Enabled)!")
    
    # Wait 3 seconds on startup before initial run to let server bind
    time.sleep(3)
    
    interval_seconds = Config.POST_INTERVAL_MINUTES * 60

    while True:
        if scheduler_running:
            try:
                # 1. Always sync live Instagram feed before checking
                storage.sync_with_instagram(publisher)

                print("[Scheduler] Checking for fresh unposted anime news...")
                # Fetch posts with game filter active
                posts = api.fetch_posts(filter_games=Config.EXCLUDE_GAME_NEWS)
                unposted = []
                for p in posts:
                    p_id = p.get("id")
                    p_link = p.get("link")
                    p_title = p.get("title")

                    if not storage.is_already_posted(p_id, link=p_link, title=p_title) and not storage.is_in_cooldown(p_id, title=p_title):
                        unposted.append(p)

                if unposted:
                    # Oldest unposted post in chronological order
                    next_p = unposted[-1]
                    p_id = next_p.get("id")
                    p_title = next_p.get("title")

                    print(f"[Scheduler] Auto-publishing: '{p_title}'")
                    
                    # Mark attempt lock immediately
                    storage.record_attempt(p_id, p_title)

                    img_url = api.get_post_image_url(next_p)
                    caption = CaptionGenerator.generate(next_p)
                    res = publisher.publish_post(img_url, caption)

                    if res["success"]:
                        storage.record_post(next_p, res.get("media_id"))
                        print(f"[Scheduler] 🎉 Successfully published '{p_title}' to Instagram (Media ID: {res.get('media_id')})!")
                        scheduler_state["last_post_time"] = datetime.now().isoformat()
                        scheduler_state["last_posted_title"] = p_title
                        scheduler_state["next_post_timestamp"] = time.time() + interval_seconds
                        
                        # Full interval sleep after successful post (e.g. 60 mins)
                        time.sleep(interval_seconds)
                    else:
                        print(f"[Scheduler Error] Failed to publish post: {res.get('error')}. Setting 15-minute cooldown before next attempt.")
                        scheduler_state["next_post_timestamp"] = time.time() + 900
                        time.sleep(900)
                else:
                    print(f"[Scheduler] All {len(posts)} pure Anime/Manga articles have already been published. Re-checking for fresh anime news in 5 minutes...")
                    scheduler_state["next_post_timestamp"] = time.time() + 300
                    time.sleep(300)
            except Exception as e:
                print(f"[Scheduler Exception] {e}")
                time.sleep(120)
        else:
            time.sleep(60)

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
        elif path == "/api/sync-instagram":
            count = storage.sync_with_instagram(publisher)
            self.send_json({"success": True, "synced_count": count, "total_posted": storage.get_posted_count()})
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
                "interval_minutes": Config.POST_INTERVAL_MINUTES,
                "exclude_game_news": Config.EXCLUDE_GAME_NEWS
            },
            "stats": {
                "total_posted": storage.get_posted_count(),
                "interval_minutes": Config.POST_INTERVAL_MINUTES,
                "aspect_ratio": Config.IMAGE_ASPECT_RATIO,
                "api_url": Config.ANIME_API_URL,
                "exclude_game_news": Config.EXCLUDE_GAME_NEWS
            }
        }

    def get_posts_data(self):
        # Sync with Instagram feed to ensure fresh status
        try:
            storage.sync_with_instagram(publisher)
        except Exception:
            pass

        # Return all posts but enrich with is_game flag
        posts = api.fetch_posts(filter_games=False)
        enriched = []
        for p in posts:
            p_id = p.get("id")
            is_posted = storage.is_already_posted(p_id, link=p.get("link"), title=p.get("title"))
            is_game = api.is_game_news(p)
            img_url = api.get_post_image_url(p)
            caption = CaptionGenerator.generate(p)
            tags = CaptionGenerator.extract_dynamic_hashtags(p)
            enriched.append({
                **p,
                "is_posted": is_posted,
                "is_game": is_game,
                "generated_image_url": img_url,
                "custom_caption": caption,
                "dynamic_hashtags": tags
            })
        return {"success": True, "count": len(enriched), "posts": enriched}

    def handle_publish_next(self):
        storage.sync_with_instagram(publisher)
        posts = api.fetch_posts(filter_games=Config.EXCLUDE_GAME_NEWS)
        unposted = [p for p in posts if not storage.is_already_posted(p.get("id"), link=p.get("link"), title=p.get("title"))]
        if not unposted:
            return {"success": False, "error": "All current anime/manga news articles have already been published!"}
        
        target = unposted[-1]
        storage.record_attempt(target.get("id"), target.get("title"))

        img_url = api.get_post_image_url(target)
        caption = CaptionGenerator.generate(target)
        res = publisher.publish_post(img_url, caption)
        if res["success"]:
            storage.record_post(target, res.get("media_id"))
            scheduler_state["last_post_time"] = datetime.now().isoformat()
            scheduler_state["last_posted_title"] = target.get("title")
            return {"success": True, "post": target, "media_id": res.get("media_id"), "permalink": res.get("permalink")}
        return {"success": False, "error": res.get("error"), "step": res.get("step")}

    def handle_publish_specific(self, post_id):
        if not post_id:
            return {"success": False, "error": "Missing post_id"}
        
        storage.sync_with_instagram(publisher)
        posts = api.fetch_posts(filter_games=False)
        target = next((p for p in posts if p.get("id") == post_id), None)
        if not target:
            return {"success": False, "error": f"Post with ID {post_id} not found in API"}
        
        if storage.is_already_posted(target.get("id"), link=target.get("link"), title=target.get("title")):
            return {"success": False, "error": f"Article '{target.get('title')}' is ALREADY published on Instagram!"}

        storage.record_attempt(target.get("id"), target.get("title"))
        img_url = api.get_post_image_url(target)
        caption = CaptionGenerator.generate(target)
        res = publisher.publish_post(img_url, caption)
        if res["success"]:
            storage.record_post(target, res.get("media_id"))
            scheduler_state["last_post_time"] = datetime.now().isoformat()
            scheduler_state["last_posted_title"] = target.get("title")
            return {"success": True, "post": target, "media_id": res.get("media_id"), "permalink": res.get("permalink")}
        return {"success": False, "error": res.get("error"), "step": res.get("step")}

def run_server(port=None):
    os.chdir(os.path.dirname(__file__))
    
    if port is None:
        port = int(os.environ.get("PORT", 5000))
        
    host = "0.0.0.0"
    
    global scheduler_thread
    scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
    scheduler_thread.start()

    server = HTTPServer((host, port), DashboardHandler)
    print(f"\n============================================================")
    print(f"  🎌 AniReport Studio Web Dashboard & Auto-Poster Active!")
    print(f"  🌐 Listening on http://{host}:{port}")
    print(f"  🚀 24/7 Zero-Duplicate & Game Filter Background Scheduler Enabled")
    print(f"============================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down cleanly...")
        server.server_close()

if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_server(p)
