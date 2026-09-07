import re
import urllib.request
from datetime import datetime
from config import Config

class CaptionGenerator:
    """Generates comprehensive, detailed, 100% English Instagram captions with announcement dates, release details, story summary, and dynamic hashtags."""

    @staticmethod
    def format_announcement_date(date_str):
        """Formats ISO date string into readable English format e.g. September 7, 2026."""
        if not date_str:
            return "Recently Announced"
        try:
            # Handle ISO formats
            clean_date = date_str.split("T")[0]
            dt = datetime.strptime(clean_date, "%Y-%m-%d")
            return dt.strftime("%B %d, %Y")
        except Exception:
            return date_str[:10]

    @staticmethod
    def extract_premiere_date(title, text=""):
        """Extracts premiere date / release timing from title and text."""
        combined = f"{title} {text}"
        
        # Patterns like 'October 3 Debut', 'premiering in Fall 2026', 'releases on October 10', 'screen in Texas This Month'
        patterns = [
            r'(?:Debuts?|Premieres?|Releases?|Air(?:s|ing)?|Stream(?:s|ing)?|Screen(?:s|ing)?)\s+(?:on|in|this)?\s*([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,\s*\d{4})?)',
            r'(?:in|on|for)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,\s*\d{4})?\s+Debut)',
            r'([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?\s+Debut)',
            r'((?:Winter|Spring|Summer|Fall|Autumn)\s+\d{4})',
            r'(?:in|on)\s+([A-Za-z]+\s+\d{4})',
            r'((?:This Month|Next Month|Early \d{4}|Late \d{4}))'
        ]

        for pat in patterns:
            match = re.search(pat, combined, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "Official Release Pending"

    @staticmethod
    def fetch_full_article_story(url):
        """Fetches detailed article paragraphs directly from source link."""
        if not url:
            return []
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=6) as res:
                html = res.read().decode('utf-8', errors='ignore')
                paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
                clean_paras = []
                for p in paragraphs:
                    clean = re.sub(r'<[^>]+>', '', p).strip()
                    # Filter ads, footers, copyrights
                    if len(clean) > 40 and not clean.startswith("Source:") and not clean.startswith("©") and not clean.startswith("Thanks to"):
                        clean_paras.append(clean)
                return clean_paras[:3]
        except Exception:
            return []

    @staticmethod
    def extract_dynamic_hashtags(post):
        """Extracts dynamic English hashtags directly from the news item, tags, title, and source."""
        hashtags = []
        seen = set()

        def add_tag(tag_str):
            if not tag_str:
                return
            cleaned = re.sub(r'[^a-zA-Z0-9_]', '', tag_str.strip())
            if cleaned and cleaned.lower() not in seen and len(cleaned) >= 2:
                seen.add(cleaned.lower())
                hashtags.append(f"#{cleaned}")

        # 1. Tags directly from API
        for tag in post.get("tags", []):
            add_tag(tag)

        # 2. Extract anime/manga names or key subjects from Title
        title = post.get("title", "")
        quoted_matches = re.findall(r"['\"‘“](.*?)['\"’”]", title)
        for q in quoted_matches:
            words = re.findall(r'[a-zA-Z0-9]+', q)
            if words:
                add_tag("".join(w.capitalize() for w in words[:4]))

        match_subject = re.search(r"^(.*?)(?:\s+(?:TV\s+)?(?:Anime|Manga|Film|Movie|Game|Franchise|Season|Video))\b", title, re.IGNORECASE)
        if match_subject:
            subject_words = re.findall(r'[a-zA-Z0-9]+', match_subject.group(1).strip())
            if subject_words and len(subject_words) <= 4:
                add_tag("".join(w.capitalize() for w in subject_words))

        # 3. Source tag
        source = post.get("source", "")
        if source:
            source_words = re.findall(r'[a-zA-Z0-9]+', source)
            if source_words:
                add_tag("".join(w.capitalize() for w in source_words))

        # 4. Badge tag
        badge = post.get("badge", "")
        if badge:
            badge_words = re.findall(r'[a-zA-Z0-9]+', badge)
            if badge_words:
                add_tag("".join(w.capitalize() for w in badge_words))

        # 5. Existing tags from API caption
        api_caption = post.get("instagram_caption", "")
        if api_caption:
            caption_tags = re.findall(r'#([a-zA-Z0-9_]+)', api_caption)
            for ct in caption_tags:
                add_tag(ct)

        # Core hashtags
        add_tag("animenews")
        add_tag("anime")
        add_tag("manga")
        add_tag("otaku")
        add_tag("animecommunity")

        return " ".join(hashtags[:15])

    @classmethod
    def generate(cls, post):
        """Builds an in-depth, rich, comprehensive 100% English Instagram caption."""
        title = post.get("title", "").strip()
        excerpt = post.get("excerpt", "").strip()
        source = post.get("source", "Anime News Network").strip()
        badge = post.get("badge", "BREAKING NEWS").strip().upper()
        date_raw = post.get("date", "")
        link = post.get("link", "")
        handle = Config.INSTAGRAM_HANDLE

        # Format announcement date & premiere timing
        announcement_date = cls.format_announcement_date(date_raw)
        
        # Try fetching full story from link
        full_paragraphs = cls.fetch_full_article_story(link)
        combined_text = " ".join(full_paragraphs) if full_paragraphs else excerpt
        premiere_timing = cls.extract_premiere_date(title, combined_text)

        # Badge emoji mapping
        badge_emojis = {
            "OFFICIAL ANNOUNCEMENT": "📢",
            "BREAKING": "🚨",
            "BREAKING NEWS": "🚨",
            "TRAILER RELEASE": "🎬",
            "OFFICIAL TRAILER": "🎬",
            "RELEASE DATE": "📅",
            "MANGA UPDATE": "📖",
            "CAST & STAFF": "👥",
            "INTERVIEW": "🎙️",
            "ANIME MOVIE": "🍿",
            "NEW VISUAL": "🎨",
        }
        emoji = badge_emojis.get(badge, "🔥")

        # Dynamic hashtags
        dynamic_hashtags = cls.extract_dynamic_hashtags(post)

        lines = [
            f"{emoji} {badge}: {title}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"📅 Announced: {announcement_date}",
            f"🎬 Release / Debut: {premiere_timing}",
            f"📌 Source: {source}",
            f"🏷️ Category: {badge.title()}",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            "📖 FULL STORY & DETAILS:"
        ]

        if full_paragraphs:
            for p in full_paragraphs[:2]:
                lines.append(p)
                lines.append("")
        elif excerpt:
            lines.append(excerpt)
            lines.append("")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            "💬 What are your thoughts on this? Are you excited for this release? Let us know in the comments below! 👇",
            "",
            f"👉 Follow {handle} for daily breaking anime news, release dates & trailer updates!",
            ".",
            ".",
            ".",
            dynamic_hashtags
        ])

        return "\n".join(lines)
