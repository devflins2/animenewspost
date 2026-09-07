import os
import json
import hashlib
from datetime import datetime
from config import Config

class Storage:
    """Manages persistent tracking of posted anime news articles to prevent duplicates."""
    
    def __init__(self, filepath=None):
        self.filepath = filepath or Config.STORAGE_FILE
        self._data = self._load()

    def _load(self):
        """Loads posted articles from JSON file."""
        if not os.path.exists(self.filepath):
            return {"posted_ids": {}, "history": []}
        
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "posted_ids" not in data:
                    data["posted_ids"] = {}
                if "history" not in data:
                    data["history"] = []
                return data
        except Exception as e:
            print(f"[Warning] Failed to load storage file: {e}. Starting with fresh in-memory data.")
            return {"posted_ids": {}, "history": []}

    def _save(self):
        """Atomically saves data to JSON file."""
        temp_filepath = f"{self.filepath}.tmp"
        try:
            with open(temp_filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            if os.path.exists(self.filepath):
                os.replace(temp_filepath, self.filepath)
            else:
                os.rename(temp_filepath, self.filepath)
        except Exception as e:
            print(f"[Error] Failed to save storage file: {e}")
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass

    def _get_hash(self, text):
        """Returns sha256 hash snippet for string."""
        if not text:
            return ""
        return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:16]

    def is_already_posted(self, post_id, link=None, title=None):
        """Checks if an article has already been posted based on ID, link, or title."""
        if not post_id and not link and not title:
            return False

        posted_ids = self._data.get("posted_ids", {})
        
        # Check by post_id
        if post_id and post_id in posted_ids:
            return True
            
        # Check by link hash
        if link:
            link_hash = f"link_{self._get_hash(link)}"
            if link_hash in posted_ids:
                return True

        # Check by title hash
        if title:
            title_hash = f"title_{self._get_hash(title)}"
            if title_hash in posted_ids:
                return True

        return False

    def record_post(self, post, instagram_media_id=None):
        """Records a post as published so it won't be posted again."""
        post_id = post.get("id")
        title = post.get("title", "")
        link = post.get("link", "")
        now_iso = datetime.now().isoformat()

        record_entry = {
            "id": post_id,
            "title": title,
            "link": link,
            "posted_at": now_iso,
            "instagram_media_id": instagram_media_id
        }

        # Index keys
        if post_id:
            self._data["posted_ids"][post_id] = now_iso
        if link:
            self._data["posted_ids"][f"link_{self._get_hash(link)}"] = now_iso
        if title:
            self._data["posted_ids"][f"title_{self._get_hash(title)}"] = now_iso

        self._data["history"].append(record_entry)
        self._save()

    def get_posted_count(self):
        """Returns total number of recorded posts in history."""
        return len(self._data.get("history", []))

    def get_recent_history(self, limit=10):
        """Returns the most recent posted records."""
        history = self._data.get("history", [])
        return history[-limit:]
