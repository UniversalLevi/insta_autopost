"""Main application entry point"""

import schedule
import time
from datetime import datetime

from .utils.config_loader import ConfigLoader
from .utils.logger import setup_logger, get_logger
from .api.rate_limiter import RateLimiter
from .services.account_service import AccountService
from .services.posting_service import PostingService
from .proxies.proxy_manager import ProxyManager
from .warming.warming_service import WarmingService
from .features.comments.comment_service import CommentService
from .features.comments.comment_monitor import CommentMonitor
from .features.comments.comment_to_dm_service import CommentToDMService

logger = get_logger(__name__)


class InstaForgeApp:
    """Main application class for Instagram management"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.config_loader = ConfigLoader(config_dir)
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
    
    def initialize(self):
        """Initialize the application"""
        logger.info("Initializing InstaForge application")
        
        # Load configuration
        self.config = self.config_loader.load_settings()
        self.accounts = self.config_loader.load_accounts()
        
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
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            requests_per_hour=self.config.instagram.rate_limit["requests_per_hour"],
            requests_per_minute=self.config.instagram.rate_limit["requests_per_minute"],
            retry_after_seconds=self.config.instagram.rate_limit["retry_after_seconds"],
        )
        
        # Initialize proxy manager
        accounts_dict = {acc.account_id: acc for acc in self.accounts}
        self.proxy_manager = ProxyManager(
            accounts=accounts_dict,
            connection_timeout=self.config.proxies.connection_timeout,
            max_retries=self.config.proxies.max_retries,
            verify_ssl=self.config.proxies.verify_ssl,
        )
        
        # Initialize account service
        self.account_service = AccountService(
            accounts=self.accounts,
            rate_limiter=self.rate_limiter,
            proxy_manager=self.proxy_manager,
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
        
        # Initialize comment automation
        self.comment_service = CommentService(
            account_service=self.account_service,
            auto_reply_enabled=True,
        )
        
        # Initialize comment-to-DM automation service
        self.comment_to_dm_service = CommentToDMService(
            account_service=self.account_service,
        )
        
        self.comment_monitor = CommentMonitor(
            account_service=self.account_service,
            comment_service=self.comment_service,
            comment_to_dm_service=self.comment_to_dm_service,
            check_interval_seconds=60,  # Check every minute
            monitor_recent_posts=5,  # Monitor last 5 posts
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
    
    def shutdown(self):
        """Gracefully shutdown the application"""
        logger.info("Shutting down InstaForge application")
        
        # Stop comment monitoring
        if self.comment_monitor:
            self.comment_monitor.stop_monitoring_all_accounts()
        
        # Close browser automation
        if hasattr(self, 'browser_wrapper') and self.browser_wrapper:
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
