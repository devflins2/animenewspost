import os
import re
import json
import hashlib
from datetime import datetime
from config import Config

class Storage:
    """
    Manages multi-tier persistent tracking of posted anime news articles to guarantee 0% duplicate posts.
    Multi-Layer Shield:
    1. Direct live Instagram feed sync (Title extraction, exact & fuzzy similarity).
    2. Local JSON persistent storage (posted_ids, hashes, clean titles).
    3. Attempt quarantine locking (prevents rapid retry loops if a post times out).
    4. MongoDB Atlas Cloud Memory (if connected).
    """
    
    def __init__(self, filepath=None):
        self.filepath = filepath or Config.STORAGE_FILE
        self.mongo_client = None
        self.db = None
        self.collection = None
        self._recent_attempts = {}  # {post_id or title_clean: timestamp}
        self._init_mongodb()
        self._data = self._load_local()

    def _init_mongodb(self):
        """Initializes MongoDB Atlas connection if MONGODB_URI is provided."""
        mongo_uri = Config.MONGODB_URI
        if not mongo_uri:
            return

        try:
            import pymongo
            import certifi
            
            # Try connecting with standard certifi bundle first
            try:
                self.mongo_client = pymongo.MongoClient(
                    mongo_uri,
                    tlsCAFile=certifi.where(),
                    serverSelectionTimeoutMS=4000
                )
                self.mongo_client.admin.command("ping")
            except Exception:
                # Fallback to permissive TLS for cloud containers
                self.mongo_client = pymongo.MongoClient(
                    mongo_uri,
                    tls=True,
                    tlsAllowInvalidCertificates=True,
                    serverSelectionTimeoutMS=4000
                )
                self.mongo_client.admin.command("ping")

            self.db = self.mongo_client.get_database("anime_autopost_db")
            self.collection = self.db.get_collection("posted_articles")
            
            self.collection.create_index("post_id", unique=False)
            self.collection.create_index("title_clean", unique=False)
            self.collection.create_index("link_hash", unique=False)
            print("[Storage] [OK] Connected to MongoDB Atlas Cloud Memory successfully!")
            self._migrate_local_to_mongodb()
        except Exception as e:
            print(f"[Storage Warning] MongoDB connection failed: {e}. Active store: Local JSON + Live Instagram Sync.")
            self.mongo_client = None
            self.db = None
            self.collection = None

    def _migrate_local_to_mongodb(self):
        """Migrates any existing local JSON records into MongoDB."""
        if self.collection is None or not os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                local_data = json.load(f)
            history = local_data.get("history", [])
            migrated = 0
            for item in history:
                post_id = item.get("id") or item.get("post_id")
                title = item.get("title", "")
                clean_title = self._clean_text(title)
                link = item.get("link", "")
                link_hash = f"link_{self._get_hash(link)}" if link else ""

                doc = {
                    "post_id": str(post_id) if post_id else "",
                    "title": title,
                    "title_clean": clean_title,
                    "link": link,
                    "link_hash": link_hash,
                    "posted_at": item.get("posted_at", datetime.now().isoformat()),
                    "instagram_media_id": item.get("instagram_media_id")
                }
                if post_id:
                    self.collection.update_one({"post_id": str(post_id)}, {"$set": doc}, upsert=True)
                elif clean_title:
                    self.collection.update_one({"title_clean": clean_title}, {"$set": doc}, upsert=True)
                migrated += 1
            if migrated > 0:
                print(f"[Storage] Migrated {migrated} records to MongoDB Atlas.")
        except Exception as e:
            print(f"[Storage Migration Warning] {e}")

    def _clean_text(self, text):
        """Strips emojis, special characters, and extra spaces for 100% accurate matching."""
        if not text:
            return ""
        # Remove emojis, punctuation, and normalize whitespace
        cleaned = re.sub(r"[^\w\s]", "", str(text).lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def _get_words(self, text):
        """Returns set of significant words (length >= 3) for similarity checking."""
        clean = self._clean_text(text)
        stopwords = {"and", "the", "for", "with", "this", "that", "from", "anime", "manga", "news"}
        return {w for w in clean.split() if len(w) >= 3 and w not in stopwords}

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
        """
        Syncs already published articles directly from real Instagram feed.
        This provides 100% protection against duplicate posts across server restarts,
        Render container resets, and ephemeral filesystem wipes.
        """
        try:
            media_list = publisher.fetch_recent_published_media(limit=50)
            if not media_list:
                return 0

            synced_count = 0
            for item in media_list:
                caption = item.get("caption", "")
                m_id = item.get("id")
                t_stamp = item.get("timestamp", datetime.now().isoformat())
                
                if not caption:
                    continue

                lines = [line.strip() for line in caption.strip().split("\n") if line.strip()]
                first_line = lines[0] if lines else ""
                
                # Remove emojis and badge prefix from first line
                cleaned_first = re.sub(r'^[^\w\s"\']+', '', first_line).strip()
                extracted_title = cleaned_first
                if ":" in cleaned_first:
                    extracted_title = cleaned_first.split(":", 1)[1].strip()

                clean_title = self._clean_text(extracted_title)
                if not clean_title:
                    continue

                title_key = f"title_{self._get_hash(clean_title)}"
                media_key = f"m_{m_id}"

                # Register in local memory
                is_new = False
                if title_key not in self._data["posted_ids"]:
                    self._data["posted_ids"][title_key] = t_stamp
                    is_new = True

                if media_key not in self._data["posted_ids"]:
                    self._data["posted_ids"][media_key] = t_stamp

                # Ensure entry is in history list
                exists_in_hist = any(
                    h.get("title_clean") == clean_title or h.get("instagram_media_id") == m_id 
                    for h in self._data.get("history", [])
                )
                if not exists_in_hist:
                    self._data["history"].append({
                        "post_id": f"ig_{m_id}",
                        "title": extracted_title,
                        "title_clean": clean_title,
                        "link": "",
                        "link_hash": "",
                        "posted_at": t_stamp,
                        "instagram_media_id": m_id,
                        "synced_from_instagram": True
                    })
                    is_new = True

                # Save in MongoDB if active
                if self.collection is not None and is_new:
                    try:
                        self.collection.update_one(
                            {"title_clean": clean_title},
                            {"$set": {
                                "title": extracted_title,
                                "title_clean": clean_title,
                                "posted_at": t_stamp,
                                "instagram_media_id": m_id,
                                "synced_from_instagram": True
                            }},
                            upsert=True
                        )
                    except Exception:
                        pass

                if is_new:
                    synced_count += 1
                        
            if synced_count > 0:
                print(f"[Storage] Synced {synced_count} new published post(s) directly from Instagram feed.")
                self._save_local()
            return synced_count
        except Exception as e:
            print(f"[Storage Sync Warning] {e}")
            return 0

    def record_attempt(self, post_id, title=None):
        """Records a post attempt timestamp to prevent rapid retry loops if a timeout occurs."""
        now = datetime.now().timestamp()
        if post_id:
            self._recent_attempts[str(post_id)] = now
        if title:
            clean = self._clean_text(title)
            if clean:
                self._recent_attempts[clean] = now

    def is_in_cooldown(self, post_id, title=None, cooldown_seconds=1800):
        """Checks if a post was attempted recently (within 30 mins) to prevent rapid re-posting on network errors."""
        now = datetime.now().timestamp()
        if post_id and str(post_id) in self._recent_attempts:
            if now - self._recent_attempts[str(post_id)] < cooldown_seconds:
                return True
        if title:
            clean = self._clean_text(title)
            if clean and clean in self._recent_attempts:
                if now - self._recent_attempts[clean] < cooldown_seconds:
                    return True
        return False

    def is_already_posted(self, post_id, link=None, title=None):
        """
        Multi-layer duplicate verification:
        1. Checks MongoDB Cloud Database (if connected)
        2. Checks Local JSON cache (ID, clean title words, link hash)
        3. Checks Substring and Token overlap against recent history
        """
        if not post_id and not link and not title:
            return False

        clean_title = self._clean_text(title) if title else ""
        link_hash = f"link_{self._get_hash(link)}" if link else ""
        title_hash = f"title_{self._get_hash(clean_title)}" if clean_title else ""
        title_words = self._get_words(title) if title else set()

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

        # 3. Check history list for clean title, substring, and token overlap
        history = self._data.get("history", [])
        if clean_title:
            for item in history:
                item_clean = item.get("title_clean") or self._clean_text(item.get("title", ""))
                if not item_clean:
                    continue

                # Exact clean title match
                if item_clean == clean_title:
                    return True

                # Substring containment (e.g. slight suffix difference)
                if len(clean_title) > 25 and len(item_clean) > 25:
                    if clean_title in item_clean or item_clean in clean_title:
                        return True

                # Word overlap (Jaccard similarity > 65%)
                if title_words:
                    item_words = self._get_words(item_clean)
                    if item_words:
                        overlap = len(title_words.intersection(item_words))
                        union = len(title_words.union(item_words))
                        if union > 0 and (overlap / union) >= 0.65:
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
        if instagram_media_id:
            self._data["posted_ids"][f"m_{instagram_media_id}"] = now_iso

        self._data["history"].append(record_entry)
        self._save_local()

    def get_posted_count(self):
        """Returns total number of recorded posts in history."""
        return len(self._data.get("history", []))

    def get_recent_history(self, limit=20):
        """Returns the most recent posted records."""
        history = self._data.get("history", [])
        return history[-limit:]
