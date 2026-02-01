"""Main application entry point"""

import schedule
import time
from datetime import datetime
from typing import Dict, Any

from .utils.config import config_manager
from .utils.logger import setup_logger, get_logger
from .api.rate_limiter import RateLimiter
from .services.account_service import AccountService
from .services.posting_service import PostingService
from .services.account_onboarding import AccountOnboardingService
from .services.account_health import AccountHealthService
from .proxies.proxy_manager import ProxyManager
from .warming.warming_service import WarmingService
from .features.comments.comment_service import CommentService
from .features.comments.comment_monitor import CommentMonitor
from .features.comments.comment_to_dm_service import CommentToDMService

logger = get_logger(__name__)


class InstaForgeApp:
    """Main application class for Instagram management"""
    
    def __init__(self, config_dir: str = "data"):
        self.config_dir = config_dir
        self.config = None
        self.accounts = []
        self.rate_limiter = None
        self.proxy_manager = None
        self.account_service = None
        self.posting_service = None
        self.warming_service = None
        self.comment_service = None
        self.comment_monitor = None
        self.comment_to_dm_service = None
        self.account_onboarding_service = None
        self.account_health_service = None
        # Expose config_manager as config_loader for backward compatibility if needed
        self.config_loader = config_manager
    
    def initialize(self):
        """Initialize the application"""
        logger.info("Initializing InstaForge application")
        
        # Load configuration
        self.config = config_manager.load_settings()
        self.accounts = config_manager.load_accounts()
        
        # Set up logging
        setup_logger(
            log_level=self.config.logging.level,
            log_format=self.config.logging.format,
            file_path=self.config.logging.file_path,
            max_bytes=self.config.logging.max_bytes,
            backup_count=self.config.logging.backup_count,
        )
        
        logger.info(
            "Configuration loaded",
            app_name=self.config.app.name,
            version=self.config.app.version,
            environment=self.config.app.environment,
            account_count=len(self.accounts),
        )
        
        # Initialize rate limiters: shared for monitor, dedicated for posting (avoids starvation)
        rl = self.config.instagram.rate_limit
        self.rate_limiter = RateLimiter(
            requests_per_hour=rl["requests_per_hour"],
            requests_per_minute=rl["requests_per_minute"],
            retry_after_seconds=rl["retry_after_seconds"],
        )
        self.rate_limiter_posting = RateLimiter(
            requests_per_hour=rl["requests_per_hour"],
            requests_per_minute=min(10, rl["requests_per_minute"]),
            retry_after_seconds=rl["retry_after_seconds"],
        )
        
        # Initialize proxy manager (shared default proxy when account has proxy.enabled but no host)
        default_proxy_url = None
        if getattr(self.config.proxies, "default_proxy", None):
            dp = self.config.proxies.default_proxy
            if dp and getattr(dp, "proxy_url", None):
                default_proxy_url = dp.proxy_url()
        accounts_dict = {acc.account_id: acc for acc in self.accounts}
        self.proxy_manager = ProxyManager(
            accounts=accounts_dict,
            connection_timeout=self.config.proxies.connection_timeout,
            max_retries=self.config.proxies.max_retries,
            verify_ssl=self.config.proxies.verify_ssl,
            default_proxy_url=default_proxy_url,
        )
        
        # Initialize account service
        posting = self.config.instagram.posting
        self.account_service = AccountService(
            accounts=self.accounts,
            rate_limiter=self.rate_limiter,
            rate_limiter_posting=self.rate_limiter_posting,
            proxy_manager=self.proxy_manager,
            image_upload_timeout=posting.get("image_upload_timeout", 90),
            video_upload_timeout=posting.get("video_upload_timeout", 180),
        )
        
        # Initialize posting service
        self.posting_service = PostingService(
            account_service=self.account_service,
            max_retries=self.config.instagram.posting["max_retries"],
            retry_delay_seconds=self.config.instagram.posting["retry_delay_seconds"],
        )
        
        # Initialize browser automation (optional, for like/follow actions)
        try:
            from .automation.browser.browser_wrapper import BrowserWrapper
            self.browser_wrapper = BrowserWrapper(headless=True)
            logger.info("Browser automation initialized")
        except ImportError as e:
            logger.warning(
                "Browser automation not available (Playwright not installed). "
                "Like/follow actions will be simulated. "
                "Install with: pip install playwright && playwright install chromium",
                error=str(e),
            )
            self.browser_wrapper = None
        except Exception as e:
            logger.warning("Failed to initialize browser automation", error=str(e))
            self.browser_wrapper = None
        
        # Initialize warming service
        self.warming_service = WarmingService(
            account_service=self.account_service,
            schedule_time=self.config.warming.schedule_time,
            randomize_delay_minutes=self.config.warming.randomize_delay_minutes,
            action_spacing_seconds=self.config.warming.action_spacing_seconds,
            browser_wrapper=self.browser_wrapper,
        )
        
        # Initialize comment-to-DM automation service (creates shared PostDMConfig)
        self.comment_to_dm_service = CommentToDMService(
            account_service=self.account_service,
        )
        
        # Initialize comment automation
        # Using global settings from config, sharing PostDMConfig for post-specific links
        self.comment_service = CommentService(
            account_service=self.account_service,
            auto_reply_enabled=self.config.comments.enabled,
            reply_templates=self.config.comments.templates,
            reply_delay_seconds=self.config.comments.delay_seconds,
            post_dm_config=self.comment_to_dm_service.post_dm_config,  # Share same config
        )
        
        self.comment_monitor = CommentMonitor(
            account_service=self.account_service,
            comment_service=self.comment_service,
            comment_to_dm_service=self.comment_to_dm_service,
            check_interval_seconds=60,  # Check every minute
            monitor_recent_posts=3,  # Fewer posts to leave headroom for posting
        )
        
        # Initialize account onboarding service
        self.account_onboarding_service = AccountOnboardingService(
            account_service=self.account_service,
            comment_monitor=self.comment_monitor,
            comment_to_dm_service=self.comment_to_dm_service,
            comment_service=self.comment_service,
        )
        
        # Initialize account health service
        self.account_health_service = AccountHealthService(
            account_service=self.account_service,
            check_interval_seconds=600,  # 10 minutes
        )
        
        logger.info("Application initialized successfully")
    
    def verify_setup(self):
        """Verify all accounts and proxies"""
        logger.info("Verifying account setup")
        
        # Verify proxies
        proxy_results = self.proxy_manager.verify_all_proxies()
        logger.info("Proxy verification completed", results=proxy_results)
        
        # Verify accounts
        account_results = self.account_service.verify_all_accounts()
        logger.info("Account verification completed", results=account_results)
        
        return {
            "proxies": proxy_results,
            "accounts": account_results,
        }
    
    def schedule_warming(self):
        """Schedule daily warming actions"""
        def run_warming():
            logger.info("Starting scheduled warming actions")
            results = self.warming_service.execute_warming_for_all_accounts()
            logger.info("Scheduled warming completed", results=results)
        
        # Parse schedule time
        hour, minute = map(int, self.config.warming.schedule_time.split(":"))
        
        # Schedule warming at specified time
        schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(run_warming)
        
        logger.info(
            "Warming actions scheduled",
            schedule_time=self.config.warming.schedule_time,
        )
    
    def run_warming_now(self):
        """Execute warming actions immediately"""
        logger.info("Executing warming actions now")
        results = self.warming_service.execute_warming_for_all_accounts()
        return results
    
    def run_scheduler(self):
        """Run the scheduler loop"""
        logger.info("Starting scheduler loop")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def reload_accounts(self) -> Dict[str, Any]:
        """
        Reload accounts from config and re-register in all services.
        
        This method:
        1. Reloads accounts from config
        2. Updates account_service with new accounts
        3. Updates proxy_manager
        4. Re-registers accounts in comment monitor
        5. Re-schedules warming (if needed)
        
        Returns:
            Dict with reload results
        """
        logger.info("Reloading accounts from config")
        
        results = {
            "accounts_loaded": 0,
            "accounts_added": [],
            "accounts_removed": [],
            "accounts_updated": [],
            "errors": [],
        }
        
        try:
            # Reload accounts from config
            new_accounts = config_manager.load_accounts()
            old_account_ids = set(self.account_service.list_accounts())
            new_account_ids = {acc.account_id for acc in new_accounts}
            
            # Find added, removed, and updated accounts
            added_ids = new_account_ids - old_account_ids
            removed_ids = old_account_ids - new_account_ids
            existing_ids = old_account_ids & new_account_ids
            
            # Update account service
            self.account_service.update_accounts(new_accounts)
            self.accounts = new_accounts
            
            # Update proxy manager (reuse same default_proxy_url from config)
            default_proxy_url = None
            if getattr(self.config.proxies, "default_proxy", None):
                dp = self.config.proxies.default_proxy
                if dp and getattr(dp, "proxy_url", None):
                    default_proxy_url = dp.proxy_url()
            accounts_dict = {acc.account_id: acc for acc in new_accounts}
            self.proxy_manager = ProxyManager(
                accounts=accounts_dict,
                connection_timeout=self.config.proxies.connection_timeout,
                max_retries=self.config.proxies.max_retries,
                verify_ssl=self.config.proxies.verify_ssl,
                default_proxy_url=default_proxy_url,
            )
            
            # Re-register accounts in comment monitor
            if self.comment_monitor:
                # Stop monitoring for removed accounts
                for account_id in removed_ids:
                    try:
                        self.comment_monitor.stop_monitoring(account_id)
                        results["accounts_removed"].append(account_id)
                        logger.info("Stopped monitoring for removed account", account_id=account_id)
                    except Exception as e:
                        logger.warning(
                            "Failed to stop monitoring for removed account",
                            account_id=account_id,
                            error=str(e),
                        )
                
                # Start monitoring for added accounts
                for account_id in added_ids:
                    try:
                        self.comment_monitor.start_monitoring(account_id)
                        results["accounts_added"].append(account_id)
                        logger.info("Started monitoring for new account", account_id=account_id)
                    except Exception as e:
                        error_msg = f"Failed to start monitoring for new account: {str(e)}"
                        results["errors"].append({"account_id": account_id, "error": error_msg})
                        logger.error("Failed to start monitoring for new account", account_id=account_id, error=str(e))
            
            # Note: Warming service and scheduler are global and automatically use all accounts
            # via account_service, so no re-registration needed
            
            results["accounts_loaded"] = len(new_accounts)
            
            logger.info(
                "Accounts reloaded successfully",
                total_accounts=len(new_accounts),
                added=len(added_ids),
                removed=len(removed_ids),
            )
        
        except Exception as e:
            error_msg = f"Failed to reload accounts: {str(e)}"
            results["errors"].append({"error": error_msg})
            logger.error("Failed to reload accounts", error=str(e))
            raise
        
        return results
    
    def shutdown(self, *, skip_browser_close: bool = False):
        """Gracefully shutdown the application.
        skip_browser_close: If True, caller has already closed browsers (e.g. web async shutdown)."""
        logger.info("Shutting down InstaForge application")
        
        # Stop health monitoring
        if self.account_health_service:
            self.account_health_service.stop_monitoring()
        
        # Stop comment monitoring
        if self.comment_monitor:
            self.comment_monitor.stop_monitoring_all_accounts()
        
        # Close browser automation (skip when web app already awaited close_all in async shutdown)
        if not skip_browser_close and hasattr(self, "browser_wrapper") and self.browser_wrapper:
            try:
                self.browser_wrapper.close_all()
            except Exception as e:
                logger.warning("Error closing browser automation", error=str(e))
        
        # Cleanup logic here if needed


def main():
    """Main entry point"""
    app = InstaForgeApp()
    
    try:
        app.initialize()
        
        # Verify setup
        verification_results = app.verify_setup()
        
        # Schedule warming actions
        app.schedule_warming()
        
        # Start comment monitoring for all accounts
        logger.info("Starting comment monitoring for all accounts")
        app.comment_monitor.start_monitoring_all_accounts()
        
        # Run scheduler
        logger.info("Application ready, starting scheduler")
        app.run_scheduler()
    
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        app.shutdown()
    except Exception as e:
        logger.error("Application error", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    main()
