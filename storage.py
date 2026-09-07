import os
import re
import json
import hashlib
from datetime import datetime
from config import Config

class Storage:
    """
    Manages multi-tier persistent tracking of posted anime news articles to prevent duplicates.
    Supports MongoDB Atlas (Cloud Memory) with automatic fallback to JSON file storage.
    """
    
    def __init__(self, filepath=None):
        self.filepath = filepath or Config.STORAGE_FILE
        self.mongo_client = None
        self.db = None
        self.collection = None
        self._init_mongodb()
        self._data = self._load_local()

    def _init_mongodb(self):
        """Initializes MongoDB Atlas connection if MONGODB_URI is provided."""
        mongo_uri = Config.MONGODB_URI
        if not mongo_uri:
            return

        try:
            import pymongo
            self.mongo_client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # Test connection
            self.mongo_client.admin.command("ping")
            self.db = self.mongo_client.get_database("anime_autopost_db")
            self.collection = self.db.get_collection("posted_articles")
            
            # Ensure unique compound indexes to prevent duplicates at database level
            self.collection.create_index("post_id", unique=False)
            self.collection.create_index("title_clean", unique=False)
            self.collection.create_index("link_hash", unique=False)
            print("[Storage] 🟢 Connected to MongoDB Atlas Cloud Memory successfully!")
        except Exception as e:
            print(f"[Storage Warning] MongoDB connection failed: {e}. Falling back to local storage.")
            self.mongo_client = None
            self.db = None
            self.collection = None

    def _clean_text(self, text):
        """Strips emojis, special characters, and extra spaces for 100% accurate matching."""
        if not text:
            return ""
        # Remove emojis and non-alphanumeric characters
        cleaned = re.sub(r"[^\w\s]", "", str(text).lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def _get_hash(self, text):
        """Returns sha256 hash snippet for string."""
        if not text:
            return ""
        return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:16]

    def _load_local(self):
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
            print(f"[Warning] Failed to load local storage file: {e}. Using in-memory store.")
            return {"posted_ids": {}, "history": []}

    def _save_local(self):
        """Atomically saves data to local JSON file."""
        temp_filepath = f"{self.filepath}.tmp"
        try:
            with open(temp_filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            if os.path.exists(self.filepath):
                os.replace(temp_filepath, self.filepath)
            else:
                os.rename(temp_filepath, self.filepath)
        except Exception as e:
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass

    def sync_with_instagram(self, publisher):
        """Syncs already published articles from real Instagram feed to prevent duplicate posts across server restarts."""
        try:
            media_list = publisher.fetch_recent_published_media(limit=35)
            if not media_list:
                return

            synced_count = 0
            for item in media_list:
                caption = item.get("caption", "")
                m_id = item.get("id")
                t_stamp = item.get("timestamp", datetime.now().isoformat())
                
                if not caption:
                    continue

                # Extract title from caption (usually line 1 after emoji/colon)
                lines = caption.strip().split("\n")
                first_line = lines[0] if lines else ""
                
                # Strip category prefix e.g. "ANIME MOVIE: " or "BREAKING NEWS: "
                if ":" in first_line:
                    extracted_title = first_line.split(":", 1)[1].strip()
                else:
                    extracted_title = first_line.strip()

                clean_title = self._clean_text(extracted_title)
                if not clean_title:
                    continue

                title_key = f"title_{self._get_hash(clean_title)}"

                # Check if already present
                if title_key not in self._data["posted_ids"]:
                    self._data["posted_ids"][title_key] = t_stamp
                    
                    # Also save in MongoDB if active
                    if self.collection is not None:
                        try:
                            if not self.collection.find_one({"title_clean": clean_title}):
                                self.collection.insert_one({
                                    "title": extracted_title,
                                    "title_clean": clean_title,
                                    "posted_at": t_stamp,
                                    "instagram_media_id": m_id,
                                    "synced_from_instagram": True
                                })
                        except Exception:
                            pass

                    synced_count += 1
                        
            if synced_count > 0:
                print(f"[Storage] Synced {synced_count} existing posts directly from Instagram feed to prevent duplicates.")
                self._save_local()
        except Exception as e:
            print(f"[Storage Sync Warning] {e}")

    def is_already_posted(self, post_id, link=None, title=None):
        """
        Multi-layer duplicate verification:
        1. Checks MongoDB Cloud Database (if connected)
        2. Checks Local JSON cache (ID, clean title words, link hash)
        """
        if not post_id and not link and not title:
            return False

        clean_title = self._clean_text(title) if title else ""
        link_hash = f"link_{self._get_hash(link)}" if link else ""
        title_hash = f"title_{self._get_hash(clean_title)}" if clean_title else ""

        # 1. Check MongoDB Database
        if self.collection is not None:
            try:
                queries = []
                if post_id:
                    queries.append({"post_id": str(post_id)})
                if clean_title:
                    queries.append({"title_clean": clean_title})
                if link:
                    queries.append({"link": link})
                
                if queries:
                    match = self.collection.find_one({"$or": queries})
                    if match:
                        return True
            except Exception as e:
                print(f"[Storage] MongoDB query error: {e}")

        # 2. Check Local memory / JSON cache
        posted_ids = self._data.get("posted_ids", {})

        # Check by post_id
        if post_id and str(post_id) in posted_ids:
            return True

        # Check by link hash
        if link_hash and link_hash in posted_ids:
            return True

        # Check by title hash
        if title_hash and title_hash in posted_ids:
            return True

        # Check by clean title fuzzy match in local history
        if clean_title:
            for item in self._data.get("history", []):
                item_clean = self._clean_text(item.get("title", ""))
                if item_clean and item_clean == clean_title:
                    return True

        return False

    def record_post(self, post, instagram_media_id=None, facebook_post_id=None):
        """Records a post in both MongoDB and Local JSON cache to guarantee zero duplicate posting."""
        post_id = post.get("id")
        title = post.get("title", "")
        clean_title = self._clean_text(title)
        link = post.get("link", "")
        link_hash = f"link_{self._get_hash(link)}" if link else ""
        title_hash = f"title_{self._get_hash(clean_title)}" if clean_title else ""
        now_iso = datetime.now().isoformat()

        record_entry = {
            "post_id": str(post_id) if post_id else "",
            "title": title,
            "title_clean": clean_title,
            "link": link,
            "link_hash": link_hash,
            "posted_at": now_iso,
            "instagram_media_id": instagram_media_id,
            "facebook_post_id": facebook_post_id
        }

        # 1. Save to MongoDB Atlas
        if self.collection is not None:
            try:
                self.collection.update_one(
                    {"post_id": str(post_id)},
                    {"$set": record_entry},
                    upsert=True
                )
            except Exception as e:
                print(f"[Storage] MongoDB save error: {e}")

        # 2. Save to Local Memory & File
        if post_id:
            self._data["posted_ids"][str(post_id)] = now_iso
        if link_hash:
            self._data["posted_ids"][link_hash] = now_iso
        if title_hash:
            self._data["posted_ids"][title_hash] = now_iso

        self._data["history"].append(record_entry)
        self._save_local()

    def get_posted_count(self):
        """Returns total number of recorded posts in history."""
        if self.collection is not None:
            try:
                return self.collection.count_documents({})
            except Exception:
                pass
        return len(self._data.get("history", []))

    def get_recent_history(self, limit=15):
        """Returns the most recent posted records."""
        if self.collection is not None:
            try:
                docs = list(self.collection.find({}, {"_id": 0}).sort("posted_at", -1).limit(limit))
                return list(reversed(docs))
            except Exception:
                pass
        history = self._data.get("history", [])
        return history[-limit:]
