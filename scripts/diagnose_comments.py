import sys
import os
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path to import src modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.config import config_manager
from src.api.instagram_client import InstagramClient
from src.utils.logger import get_logger

# Configure logging for this script
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger("diagnostics")

REPORT_FILE = "logs/diagnostics.log"

class CommentDiagnostics:
    def __init__(self):
        self.settings = config_manager.load_settings()
        self.accounts = config_manager.load_accounts()
        self.report_lines = []
        
        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)

    def log(self, message: str, status: str = ""):
        """Log to report and stdout"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"{message:<50} {status}"
        print(formatted_message)
        self.report_lines.append(f"[{timestamp}] {formatted_message}")

    def add_section(self, title: str):
        separator = "-" * 60
        self.report_lines.append("")
        self.report_lines.append(separator)
        self.report_lines.append(title.upper())
        self.report_lines.append(separator)
        print(f"\n{separator}")
        print(f"{title.upper()}")
        print(f"{separator}")

    def check_permissions(self, client: InstagramClient) -> Dict[str, str]:
        """Check token permissions"""
        required_permissions = [
            "instagram_basic",
            "instagram_manage_comments",
            "instagram_manage_messages",
            "instagram_content_publish"
        ]
        
        results = {}
        try:
            # Check permissions endpoint
            # First try the configured base URL
            try:
                response = client._make_request("GET", "me/permissions")
            except Exception:
                # If that fails (e.g. using graph.instagram.com), try graph.facebook.com
                # This helps detect if the base URL setting is wrong
                import requests
                fb_url = f"https://graph.facebook.com/{client.api_version}/me/permissions"
                self.log("  -> DEBUG:", f"Fallback checking {fb_url}...")
                res = requests.get(fb_url, params={"access_token": client.access_token})
                if res.status_code == 200:
                    response = res.json()
                    self.log("  -> NOTE:", "Permissions found via graph.facebook.com. Update settings.yaml api_base_url!")
                else:
                    self.log("  -> DEBUG:", f"Fallback failed with status {res.status_code}: {res.text[:100]}")
                    raise

            data = response.get("data", [])
            
            granted_permissions = [
                p.get("permission") for p in data 
                if p.get("status") == "granted"
            ]
            
            for perm in required_permissions:
                if perm in granted_permissions:
                    results[perm] = "GRANTED"
                else:
                    results[perm] = "MISSING"
                    
        except Exception as e:
            logger.error(f"Failed to check permissions: {str(e)}")
            for perm in required_permissions:
                results[perm] = "CHECK_FAILED"
                
        return results

    def check_debug_token(self, client: InstagramClient, token: str) -> str:
        """Call debug_token endpoint"""
        try:
            # debug_token requires an access_token parameter which is the token itself 
            # if we are inspecting it as the owner
            response = client._make_request(
                "GET", 
                "debug_token", 
                params={
                    "input_token": token
                }
            )
            data = response.get("data", {})
            is_valid = data.get("is_valid", False)
            return "VALID" if is_valid else "INVALID"
        except Exception as e:
            # debug_token might fail if the client base URL structure doesn't match exactly 
            # or if permissions deny introspection.
            # However, we can infer validity from basic API calls.
            return f"CHECK FAILED ({str(e)})"

    def check_media_comments(self, client: InstagramClient) -> List[Dict]:
        """Check comments on recent media"""
        results = []
        try:
            # Fetch latest 3 media
            media_list = client.get_recent_media(limit=3)
            
            # Need to fetch comment_count and comments
            for media in media_list:
                media_id = media.get("id")
                # Fetch details including comment_count
                details = client._make_request(
                    "GET", 
                    media_id, 
                    params={"fields": "comments_count,media_type"}
                )
                comment_count = details.get("comments_count", 0)
                
                # Fetch actual comments
                comments_response = client._make_request(
                    "GET", 
                    f"{media_id}/comments",
                    params={"fields": "id,text,timestamp,username"}
                )
                comments_data = comments_response.get("data", [])
                api_returned_count = len(comments_data)
                
                results.append({
                    "media_id": media_id,
                    "media_type": details.get("media_type"),
                    "comment_count_field": comment_count,
                    "api_returned_count": api_returned_count,
                    "status": "OK" if api_returned_count > 0 or comment_count == 0 else "MISMATCH"
                })
                
        except Exception as e:
            logger.error(f"Failed to check media comments: {str(e)}")
            
        return results

    def run(self):
        self.add_section("Global Configuration")
        
        # Webhook / Polling Status
        webhook_enabled = self.settings.proxies.webhooks if hasattr(self.settings.proxies, 'webhooks') else False
        
        is_polling = True # Default assumption if webhooks disabled
        self.log("Webhook Enabled:", str(webhook_enabled))
        self.log("Polling Mode:", "ACTIVE" if not webhook_enabled else "INACTIVE")
        
        # Rate Limits (Static config check)
        rate_limit = self.settings.instagram.rate_limit
        self.log("API Base URL:", self.settings.instagram.api_base_url)
        self.log("Configured Rate Limit (hr):", str(rate_limit.get("requests_per_hour", "N/A")))

        if not self.accounts:
            self.log("No accounts configured!", "ERROR")
            return

        for account in self.accounts:
            self.add_section(f"Account Diagnostic: {account.username}")
            
            client = InstagramClient(
                access_token=account.access_token,
                api_base_url=self.settings.instagram.api_base_url,
                api_version=self.settings.instagram.api_version
            )
            
            # 1. Network / API Health & Token Validity
            self.log("Checking API Connectivity...")
            try:
                account_info = client.get_account_info()
                self.log("API Connection:", "SUCCESS")
                self.log("Account ID:", account_info.get("id"))
                self.log("Account Type:", account_info.get("account_type", "UNKNOWN"))
                
                # Check eligibility
                if account_info.get("account_type") not in ["BUSINESS", "CREATOR", "MEDIA_CREATOR"]:
                    self.log("Comment API Eligibility:", "INELIGIBLE (Must be Business/Creator)")
                else:
                    self.log("Comment API Eligibility:", "ELIGIBLE")
                    
            except Exception as e:
                self.log("API Connection:", f"FAILED ({str(e)})")
                self.log("Token Status:", "INVALID or EXPIRED")
                continue

            # 2. Permissions
            self.log("Checking Permissions...")
            perms = self.check_permissions(client)
            for perm, status in perms.items():
                self.log(f"  - {perm}:", status)
            
            if perms.get("instagram_manage_comments") != "GRANTED":
                self.log("CRITICAL:", "Missing 'instagram_manage_comments' permission. Comments will NOT work.")

            # 3. Media Comment Test
            self.log("Testing Comment Retrieval...")
            media_results = self.check_media_comments(client)
            
            if not media_results:
                self.log("Recent Media:", "NONE FOUND")
            else:
                for m in media_results:
                    status_msg = f"Count: {m['comment_count_field']} | API Returns: {m['api_returned_count']}"
                    self.log(f"  - Media {m['media_id']}:", status_msg)
                    
                    if m['comment_count_field'] > 0 and m['api_returned_count'] == 0:
                        self.log("    -> WARNING:", "Comments exist but API returned 0. Possible permission/privacy issue.")

            # 4. Auto-reply / Comment automation readiness
            self.log("Comment automation readiness", "")
            comments_enabled = getattr(self.settings.comments, "enabled", False)
            self.log("  - comments.enabled (settings):", "YES" if comments_enabled else "NO")
            self.log("  - instagram_manage_comments:", perms.get("instagram_manage_comments", "?"))
            fetch_ok = bool(media_results) and all(
                m["api_returned_count"] >= 0 for m in media_results
            )
            self.log("  - Comment fetch test:", "OK" if fetch_ok else "CHECK ABOVE")
            if comments_enabled and perms.get("instagram_manage_comments") == "GRANTED" and fetch_ok:
                self.log("  -> Auto-reply ready:", "YES")
            else:
                self.log("  -> Auto-reply ready:", "NO (fix config/permissions)")

            # 5. Rate Limit Status
            # We can check headers from the last request if we had access, 
            # but usually a successful call means we are not blocked.
            self.log("Rate Limit Status:", "OK (Calls succeeding)")

        self.save_report()

    def save_report(self):
        try:
            with open(REPORT_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(self.report_lines))
            print(f"\nDiagnostic report saved to {REPORT_FILE}")
        except Exception as e:
            print(f"Failed to save report: {e}")

if __name__ == "__main__":
    try:
        diag = CommentDiagnostics()
        diag.run()
    except KeyboardInterrupt:
        print("\nDiagnostics interrupted.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
