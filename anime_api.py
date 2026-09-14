import re
import time
import requests
import urllib.parse
from config import Config

class AnimeNewsAPI:
    """Client for fetching Anime News articles and filtering out non-anime/gaming posts."""

    def __init__(self):
        self.api_url = Config.ANIME_API_URL
        self.ratio = Config.IMAGE_ASPECT_RATIO
        self.handle = Config.INSTAGRAM_HANDLE

    @staticmethod
    def is_game_news(post):
        """
        Detects if an article is specifically about video games / gaming (console, mobile, PC).
        Preserves Anime / Manga news even if titles contain words like 'Game' (e.g. No Game No Life, Darwin's Game).
        """
        title = post.get("title", "")
        excerpt = post.get("excerpt", "")
        tags = [t.lower() for t in post.get("tags", [])]

        # 1. Video game specific actions / phrases in title
        game_action_patterns = [
            r"\b(?:Game\'s\s+(?:Overview|Trailer|Video|Promo|Gameplay|Battle|Update|Opening|DLC|Demo|Character|Prequel|System))\b",
            r"\b(?:Mobile\s+Game|Smartphone\s+Game|Console\s+Game|Browser\s+Game|PC\s+Game|Gacha\s+Game|Action-RPG\s+Game|VR\s+Game)\b",
            r"\b(?:Game\s+Pre-Registration|Game\s+Launches|Game\s+Releases|Game\s+Slated|Game\s+Gets\s+DLC|Game\s+Adds|Game\s+Highlights)\b",
            r"\b(?:Gameplay|Playable\s+Demo|Early\s+Access|Closed\s+Beta|Open\s+Beta)\b",
            r"\b(?:PlayStation|PS5|PS4|Nintendo\s+Switch|Xbox|Steam|iOS/Android|iOS\s+and\s+Android|Genshin\s+Impact|Honkai|Fate/Grand\s+Order|Pokemon\s+GO)\b",
            r"\b(?:Developer|Studio)\s+(?:Game\s+Freak|Bandai\s+Namco\s+Games|Capcom|Square\s+Enix\s+Games|Koei\s+Tecmo|Mihoyo|Hoyoverse)\b",
            r"\b(?:Announces|Launches|Releases|Previews)\s+.*?\b(?:Mobile\s+Game|Smartphone\s+Game|Action\s+Game|RPG\s+Game|Gacha\s+Game)\b"
        ]

        for pat in game_action_patterns:
            if re.search(pat, title, re.IGNORECASE):
                # If it's strictly an Anime adaptation announcement e.g. "Game Gets TV Anime"
                if re.search(r'\b(?:Gets\s+(?:TV\s+)?Anime|Anime\s+Adaptation\s+Announced)\b', title, re.IGNORECASE) and not re.search(r'\b(?:Gameplay|Game\'s\s+Overview|Game\'s\s+Video|Mobile\s+Game)\b', title, re.IGNORECASE):
                    continue
                return True

        # 2. Check title ending or structure like '... Game' without Anime/Manga indicators
        if re.search(r'\bGame\b', title, re.IGNORECASE):
            # If title does NOT mention Anime, Manga, Film, Movie, TV, OVA, Season, Manga Plus, Volume
            if not re.search(r'\b(?:Anime|Manga|Film|Movie|TV\s+Series|OVA|OAD|Season|Episode|Chapter|Manga\s+Plus|Comic)\b', title, re.IGNORECASE):
                return True

        # 3. Excerpt inspection
        game_excerpt_patterns = [
            r"\b(?:gameplay|playable character|pre-registration for the game|free-to-play mobile game|launches for iOS and Android|available on Steam|game will be available for PlayStation|Nintendo Switch and PC)\b"
        ]
        for pat in game_excerpt_patterns:
            if re.search(pat, excerpt, re.IGNORECASE):
                if not re.search(r'\b(?:TV\s+Anime|Anime\s+Series|Anime\s+Film|Manga\s+Ends|Manga\s+Launches)\b', title, re.IGNORECASE):
                    return True

        return False

    def fetch_posts(self, filter_games=None):
        """Fetches the latest anime news posts with retry logic and optional game filtering."""
        if filter_games is None:
            filter_games = Config.EXCLUDE_GAME_NEWS

        headers = {
            "User-Agent": "AnimeNewsInstagramBot/1.0",
            "Accept": "application/json"
        }

        for attempt in range(1, Config.MAX_RETRIES + 1):
            try:
                print(f"[API] Fetching anime news from {self.api_url} (Attempt {attempt}/{Config.MAX_RETRIES})...")
                response = requests.get(self.api_url, headers=headers, timeout=45)
                
                if response.status_code == 200:
                    data = response.json()
                    posts = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    print(f"[API] Successfully fetched {len(posts)} articles.")
                    
                    if filter_games:
                        original_count = len(posts)
                        filtered = [p for p in posts if not self.is_game_news(p)]
                        game_count = original_count - len(filtered)
                        if game_count > 0:
                            print(f"[API Filter] Filtered out {game_count} gaming/video game article(s). {len(filtered)} pure Anime/Manga articles remain.")
                        return filtered

                    return posts
                else:
                    print(f"[API Warning] HTTP {response.status_code} returned: {response.text[:200]}")
            except requests.exceptions.RequestException as e:
                print(f"[API Error] Request failed on attempt {attempt}: {e}")

            if attempt < Config.MAX_RETRIES:
                print(f"[API] Waiting {Config.RETRY_DELAY_SECONDS}s before retrying...")
                time.sleep(Config.RETRY_DELAY_SECONDS)

        print("[API Error] Failed to fetch posts after max retries.")
        return []

    def get_post_image_url(self, post):
        """Constructs an HTTPS image URL for Instagram container creation."""
        post_id = post.get("id")
        if not post_id:
            return None

        # Build custom rendered image URL with handle and aspect ratio
        encoded_handle = urllib.parse.quote(self.handle)
        encoded_ratio = urllib.parse.quote(self.ratio)
        
        # Base origin
        parsed = urllib.parse.urlparse(self.api_url)
        base_origin = f"https://{parsed.netloc}"
        
        image_url = f"{base_origin}/api/v1/posts/{post_id}/image?ratio={encoded_ratio}&handle={encoded_handle}"
        return image_url
