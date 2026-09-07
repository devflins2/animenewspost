import time
import requests
import urllib.parse
from config import Config

class AnimeNewsAPI:
    """Client for fetching Anime News articles and generated image URLs."""

    def __init__(self):
        self.api_url = Config.ANIME_API_URL
        self.ratio = Config.IMAGE_ASPECT_RATIO
        self.handle = Config.INSTAGRAM_HANDLE

    def fetch_posts(self):
        """Fetches the latest anime news posts with retry logic for server cold starts."""
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
