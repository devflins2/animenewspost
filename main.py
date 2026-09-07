import os
import sys
import time
import argparse
import warnings
from datetime import datetime

# Configure UTF-8 encoding for Windows Console to support Emojis and Unicode
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Suppress minor dependency version warnings
warnings.filterwarnings("ignore")

from colorama import init, Fore, Style
from config import Config
from storage import Storage
from anime_api import AnimeNewsAPI
from instagram_publisher import InstagramPublisher
from caption_generator import CaptionGenerator

# Initialize Colorama
init(autoreset=True)

class AnimeNewsAutoPostBot:
    def __init__(self):
        self.storage = Storage()
        self.api = AnimeNewsAPI()
        self.publisher = InstagramPublisher()

    def print_banner(self):
        print(f"""{Fore.CYAN}
============================================================
              ANIME NEWS INSTAGRAM AUTOPOST
                 24/7 Automated Publisher
============================================================{Style.RESET_ALL}
""")

    def verify_setup(self):
        """Verifies environment variables and Instagram account access."""
        if not Config.validate():
            return False

        print(f"{Fore.YELLOW}[Setup] Verifying Instagram connection...{Style.RESET_ALL}")
        account_info = self.publisher.verify_account()
        
        if not account_info["success"]:
            print(f"{Fore.RED}[Error] Instagram Token verification failed: {account_info['error']}{Style.RESET_ALL}")
            return False

        print(f"{Fore.GREEN}[OK] Instagram Account Connected!{Style.RESET_ALL}")
        print(f"  • Username     : {Fore.CYAN}@{account_info['username']}{Style.RESET_ALL}")
        print(f"  • Account ID   : {Fore.CYAN}{account_info['id']}{Style.RESET_ALL}")
        print(f"  • Account Type : {Fore.CYAN}{account_info['account_type']}{Style.RESET_ALL}")
        print(f"  • Post Interval: {Fore.CYAN}Every {Config.POST_INTERVAL_MINUTES} minute(s){Style.RESET_ALL}")
        print(f"  • Total Posted : {Fore.CYAN}{self.storage.get_posted_count()} articles recorded{Style.RESET_ALL}")
        print("-" * 60)
        return True

    def find_next_post_to_publish(self):
        """Fetches news and returns the next unposted article."""
        posts = self.api.fetch_posts()
        if not posts:
            print(f"{Fore.YELLOW}[Bot] No articles retrieved from Anime News API.{Style.RESET_ALL}")
            return None

        # Filter unposted articles
        unposted = []
        for p in posts:
            p_id = p.get("id")
            p_link = p.get("link")
            p_title = p.get("title")
            
            if not self.storage.is_already_posted(p_id, link=p_link, title=p_title):
                unposted.append(p)

        if not unposted:
            print(f"{Fore.YELLOW}[Bot] All {len(posts)} fetched articles have already been posted! No new article to publish.{Style.RESET_ALL}")
            return None

        # Pick the oldest unposted post (chronological order) so all news is posted in sequence
        next_post = unposted[-1]
        print(f"{Fore.GREEN}[Bot] Found {len(unposted)} unposted article(s). Selected: '{next_post.get('title')}'{Style.RESET_ALL}")
        return next_post

    def run_post_cycle(self, dry_run=False):
        """Executes a single check and post workflow."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{Fore.BLUE}==================== [Cycle: {timestamp}] ===================={Style.RESET_ALL}")

        post = self.find_next_post_to_publish()
        if not post:
            print(f"{Fore.YELLOW}[Bot] Cycle completed with no new posts. Waiting for next cycle...{Style.RESET_ALL}")
            return False

        post_id = post.get("id")
        title = post.get("title")
        image_url = self.api.get_post_image_url(post)
        caption = CaptionGenerator.generate(post)

        print(f"\n{Fore.MAGENTA}Article Details:{Style.RESET_ALL}")
        print(f"  • ID    : {post_id}")
        print(f"  • Title : {title}")
        print(f"  • Image : {image_url}")
        print(f"\n{Fore.MAGENTA}Generated Caption:{Style.RESET_ALL}\n{caption}\n")

        if dry_run:
            print(f"{Fore.CYAN}[DRY-RUN] Test mode active. Skipping actual Instagram API call.{Style.RESET_ALL}")
            return True

        # Publish to Instagram
        print(f"{Fore.CYAN}[Publishing] Sending post to Instagram...{Style.RESET_ALL}")
        result = self.publisher.publish_post(image_url, caption)

        if result["success"]:
            media_id = result.get("media_id")
            permalink = result.get("permalink", "N/A")
            
            # Record post to prevent duplicate
            self.storage.record_post(post, instagram_media_id=media_id)
            
            print(f"\n{Fore.GREEN}[SUCCESS] Post Published Successfully to Instagram!{Style.RESET_ALL}")
            print(f"  • Media ID  : {Fore.CYAN}{media_id}{Style.RESET_ALL}")
            print(f"  • Permalink : {Fore.CYAN}{permalink}{Style.RESET_ALL}")
            print(f"  • Total Posted so far: {Fore.GREEN}{self.storage.get_posted_count()}{Style.RESET_ALL}")
            return True
        else:
            print(f"\n{Fore.RED}[FAILED] Unable to publish post:{Style.RESET_ALL}")
            print(f"  • Step  : {result.get('step')}")
            print(f"  • Error : {result.get('error')}")
            return False

    def display_status(self):
        """Displays current status and history."""
        self.print_banner()
        if not self.verify_setup():
            return

        history = self.storage.get_recent_history(limit=5)
        print(f"\n{Fore.CYAN}Last {len(history)} Published Posts:{Style.RESET_ALL}")
        if not history:
            print("  (No posts recorded yet in history)")
        else:
            for idx, h in enumerate(reversed(history), 1):
                print(f"  {idx}. [{h.get('posted_at')[:19]}] {h.get('title')}")
                if h.get('instagram_media_id'):
                    print(f"     Media ID: {h.get('instagram_media_id')}")

    def start_scheduler(self):
        """Starts continuous 24/7 loop with hourly scheduler."""
        self.print_banner()
        if not self.verify_setup():
            print(f"{Fore.RED}[Exit] Please fix configuration issues in .env to continue.{Style.RESET_ALL}")
            return

        interval_seconds = Config.POST_INTERVAL_MINUTES * 60
        print(f"\n{Fore.GREEN}[RUNNING] Bot is active in 24/7 Auto-Post Mode!{Style.RESET_ALL}")
        print(f"Checking every {Config.POST_INTERVAL_MINUTES} minute(s) ({interval_seconds}s). Press Ctrl+C to stop.\n")

        # Run first cycle immediately on startup
        self.run_post_cycle(dry_run=False)

        while True:
            try:
                # Countdown before next cycle
                next_run_time = datetime.now().timestamp() + interval_seconds
                while datetime.now().timestamp() < next_run_time:
                    remaining = int(next_run_time - datetime.now().timestamp())
                    mins, secs = divmod(remaining, 60)
                    hrs, mins = divmod(mins, 60)
                    sys.stdout.write(f"\r{Fore.LIGHTBLACK_EX}Next auto-post check in: {hrs:02d}h {mins:02d}m {secs:02d}s...{Style.RESET_ALL} ")
                    sys.stdout.flush()
                    time.sleep(1)
                
                print() # Newline after countdown
                self.run_post_cycle(dry_run=False)

            except KeyboardInterrupt:
                print(f"\n\n{Fore.YELLOW}[Bot Stopped] Exiting cleanly...{Style.RESET_ALL}")
                break
            except Exception as e:
                print(f"\n{Fore.RED}[Unexpected Error] {e}{Style.RESET_ALL}")
                print(f"[Bot] Resuming in 60 seconds...")
                time.sleep(60)

def main():
    parser = argparse.ArgumentParser(description="Anime News Instagram Auto-Post Bot")
    parser.add_argument("--post-now", "--once", action="store_true", help="Fetch news and publish 1 post immediately, then exit")
    parser.add_argument("--dry-run", action="store_true", help="Test fetch and caption generation without publishing to Instagram")
    parser.add_argument("--status", action="store_true", help="Display bot status, Instagram account info, and post history")
    args = parser.parse_args()

    bot = AnimeNewsAutoPostBot()

    if args.status:
        bot.display_status()
    elif args.dry_run:
        bot.print_banner()
        bot.verify_setup()
        bot.run_post_cycle(dry_run=True)
    elif args.post_now:
        bot.print_banner()
        if bot.verify_setup():
            bot.run_post_cycle(dry_run=False)
    else:
        # Default: Continuous 24/7 mode
        bot.start_scheduler()

if __name__ == "__main__":
    main()
