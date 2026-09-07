import time
import requests
from config import Config

class InstagramPublisher:
    """Handles Instagram Graph API publishing operations for Business/Creator accounts."""

    def __init__(self):
        self.access_token = Config.INSTAGRAM_ACCESS_TOKEN
        self.account_id = Config.INSTAGRAM_ACCOUNT_ID
        self.base_url = "https://graph.instagram.com/v21.0"

    def verify_account(self):
        """Verifies the Instagram access token and resolves the account ID."""
        try:
            url = f"{self.base_url}/me"
            params = {
                "fields": "id,username,account_type",
                "access_token": self.access_token
            }
            res = requests.get(url, params=params, timeout=15)
            data = res.json()
            
            if res.status_code == 200 and "id" in data:
                if not self.account_id:
                    self.account_id = data["id"]
                return {
                    "success": True,
                    "id": data["id"],
                    "username": data.get("username", "Unknown"),
                    "account_type": data.get("account_type", "Unknown")
                }
            else:
                error_msg = data.get("error", {}).get("message", res.text)
                return {"success": False, "error": error_msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def fetch_recent_published_media(self, limit=25):
        """Fetches recent published posts directly from the Instagram account."""
        if not self.account_id:
            self.verify_account()

        try:
            url = f"{self.base_url}/{self.account_id}/media"
            params = {
                "fields": "id,caption,timestamp,permalink",
                "limit": limit,
                "access_token": self.access_token
            }
            res = requests.get(url, params=params, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data.get("data", [])
        except Exception as e:
            print(f"[Instagram Sync Warning] Could not fetch live feed: {e}")
        return []

    def create_media_container(self, image_url, caption):
        """Creates an Instagram media container with the image and caption."""
        if not self.account_id:
            acc_info = self.verify_account()
            if not acc_info["success"]:
                return {"success": False, "error": f"Failed to resolve Account ID: {acc_info['error']}"}

        url = f"{self.base_url}/{self.account_id}/media"
        payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.access_token
        }

        try:
            res = requests.post(url, data=payload, timeout=30)
            data = res.json()
            if res.status_code == 200 and "id" in data:
                return {"success": True, "container_id": data["id"]}
            else:
                error_msg = data.get("error", {}).get("message", res.text)
                return {"success": False, "error": error_msg, "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def wait_for_container_ready(self, container_id, max_attempts=12, delay_seconds=4):
        """Polls container status until Meta finishes processing the image."""
        url = f"{self.base_url}/{container_id}"
        params = {
            "fields": "status_code,status",
            "access_token": self.access_token
        }

        for i in range(max_attempts):
            try:
                res = requests.get(url, params=params, timeout=15)
                data = res.json()
                status_code = data.get("status_code", "").upper()

                if status_code == "FINISHED":
                    return {"success": True}
                elif status_code in ["ERROR", "EXPIRED"]:
                    return {"success": False, "error": f"Container status returned {status_code}"}
                
                time.sleep(delay_seconds)
            except Exception as e:
                time.sleep(delay_seconds)

        return {"success": False, "error": "Container processing timed out."}

    def publish_media_container(self, container_id):
        """Publishes the processed media container to the user's feed."""
        url = f"{self.base_url}/{self.account_id}/media_publish"
        payload = {
            "creation_id": container_id,
            "access_token": self.access_token
        }

        try:
            res = requests.post(url, data=payload, timeout=30)
            data = res.json()
            if res.status_code == 200 and "id" in data:
                return {"success": True, "media_id": data["id"]}
            else:
                error_msg = data.get("error", {}).get("message", res.text)
                return {"success": False, "error": error_msg, "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_post_permalink(self, media_id):
        """Retrieves permalink URL of the published Instagram post."""
        try:
            url = f"{self.base_url}/{media_id}"
            params = {
                "fields": "permalink,timestamp",
                "access_token": self.access_token
            }
            res = requests.get(url, params=params, timeout=15)
            data = res.json()
            return data.get("permalink")
        except Exception:
            return None

    def publish_post(self, image_url, caption):
        """Executes full publishing workflow: container creation -> status check -> publication."""
        print("[Instagram] 1/3 Creating media container...")
        c_res = self.create_media_container(image_url, caption)
        if not c_res["success"]:
            return {"success": False, "step": "create_container", "error": c_res["error"]}

        container_id = c_res["container_id"]
        print(f"[Instagram] Media container created (ID: {container_id}). Waiting for Meta processing...")

        print("[Instagram] 2/3 Checking processing status...")
        status_res = self.wait_for_container_ready(container_id)
        if not status_res["success"]:
            return {"success": False, "step": "status_check", "error": status_res["error"]}

        print("[Instagram] 3/3 Publishing media container to feed...")
        pub_res = self.publish_media_container(container_id)
        if not pub_res["success"]:
            return {"success": False, "step": "media_publish", "error": pub_res["error"]}

        media_id = pub_res["media_id"]
        permalink = self.get_post_permalink(media_id)

        return {
            "success": True,
            "media_id": media_id,
            "permalink": permalink
        }
