import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class Config:
    """Application configuration loaded from environment variables."""
    
    # Instagram Credentials from .env
    INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
    INSTAGRAM_HANDLE = os.getenv("INSTAGRAM_HANDLE", "@anireport_").strip()
    
    # Anime News API
    ANIME_API_URL = os.getenv("ANIME_API_URL", "https://animeapinews.onrender.com/api/v1/posts").strip()
    IMAGE_ASPECT_RATIO = os.getenv("IMAGE_ASPECT_RATIO", "4:5").strip()
    
    # Exclude video game / gaming news (Focus 100% on Anime & Manga)
    EXCLUDE_GAME_NEWS = os.getenv("EXCLUDE_GAME_NEWS", "true").strip().lower() in ("true", "1", "yes")
    
    try:
        POST_INTERVAL_MINUTES = int(os.getenv("POST_INTERVAL_MINUTES", "60"))
    except ValueError:
        POST_INTERVAL_MINUTES = 60
        
    try:
        MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    except ValueError:
        MAX_RETRIES = 3
        
    try:
        RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "15"))
    except ValueError:
        RETRY_DELAY_SECONDS = 15

    # MongoDB Atlas Persistent Cloud Storage
    MONGODB_URI = os.getenv("MONGODB_URI", os.getenv("MONGO_URI", "")).strip()

    STORAGE_FILE = os.path.join(os.path.dirname(__file__), "posted_articles.json")

    @classmethod
    def validate(cls):
        """Validate required configuration values."""
        errors = []
        if not cls.INSTAGRAM_ACCESS_TOKEN:
            errors.append("INSTAGRAM_ACCESS_TOKEN is required in .env")
        if not cls.ANIME_API_URL:
            errors.append("ANIME_API_URL is required in .env")
            
        if errors:
            print("Configuration Error(s):")
            for err in errors:
                print(f" - {err}")
            return False
        return True
