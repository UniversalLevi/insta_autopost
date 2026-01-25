"""Account management service with isolation"""

from typing import Dict, List, Optional
from threading import Lock
from tenacity import RetryError

from ..models.account import Account
from ..api.instagram_client import InstagramClient
from ..api.rate_limiter import RateLimiter
from ..utils.logger import get_logger
from ..utils.exceptions import AccountError, InstagramAPIError
from ..proxies.proxy_manager import ProxyManager

logger = get_logger(__name__)


class AccountService:
    """Service for managing Instagram accounts with isolation"""
    
    def __init__(
        self,
        accounts: List[Account],
        rate_limiter: Optional[RateLimiter] = None,
        rate_limiter_posting: Optional[RateLimiter] = None,
        proxy_manager: Optional[ProxyManager] = None,
        image_upload_timeout: int = 90,
        video_upload_timeout: int = 180,
    ):
        self.accounts = {acc.account_id: acc for acc in accounts}
        self.clients: Dict[str, InstagramClient] = {}
        self.posting_clients: Dict[str, InstagramClient] = {}
        self.lock = Lock()
        self.rate_limiter = rate_limiter
        self.rate_limiter_posting = rate_limiter_posting or rate_limiter
        self.proxy_manager = proxy_manager
        self.image_upload_timeout = image_upload_timeout
        self.video_upload_timeout = video_upload_timeout
        
        # Initialize clients for each account
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Instagram clients for all accounts"""
        for account_id, account in self.accounts.items():
            try:
                # Get proxy URL if enabled
                proxy_url = None
                if account.proxy.enabled:
                    if self.proxy_manager:
                        proxy_url = self.proxy_manager.get_proxy_url(account_id)
                    else:
                        proxy_url = account.proxy.proxy_url
                
                # Create client for monitoring (comment / media fetch)
                client = InstagramClient(
                    access_token=account.access_token,
                    rate_limiter=self.rate_limiter,
                    proxy_url=proxy_url,
                    image_upload_timeout=self.image_upload_timeout,
                    video_upload_timeout=self.video_upload_timeout,
                )
                self.clients[account_id] = client
                
                # Create posting-only client with dedicated rate limiter (avoids starvation)
                posting_client = InstagramClient(
                    access_token=account.access_token,
                    rate_limiter=self.rate_limiter_posting,
                    proxy_url=proxy_url,
                    image_upload_timeout=self.image_upload_timeout,
                    video_upload_timeout=self.video_upload_timeout,
                )
                self.posting_clients[account_id] = posting_client
                
                logger.info(
                    "Initialized account client",
                    account_id=account_id,
                    username=account.username,
                    has_proxy=bool(proxy_url),
                )
            
            except Exception as e:
                logger.error(
                    "Failed to initialize account client",
                    account_id=account_id,
                    error=str(e),
                )
                raise AccountError(f"Failed to initialize client for {account_id}: {str(e)}")
    
    def get_client(self, account_id: str) -> InstagramClient:
        """
        Get Instagram client for an account
        
        Args:
            account_id: Account identifier
            
        Returns:
            InstagramClient instance
            
        Raises:
            AccountError: If account not found
        """
        if account_id not in self.clients:
            raise AccountError(f"Account not found: {account_id}")
        
        return self.clients[account_id]
    
    def get_posting_client(self, account_id: str) -> InstagramClient:
        """
        Get Instagram client for posting (uses dedicated rate limiter).
        
        Args:
            account_id: Account identifier
            
        Returns:
            InstagramClient instance
            
        Raises:
            AccountError: If account not found
        """
        if account_id not in self.posting_clients:
            raise AccountError(f"Account not found: {account_id}")
        
        return self.posting_clients[account_id]
    
    def get_account(self, account_id: str) -> Account:
        """
        Get account configuration
        
        Args:
            account_id: Account identifier
            
        Returns:
            Account instance
            
        Raises:
            AccountError: If account not found
        """
        if account_id not in self.accounts:
            raise AccountError(f"Account not found: {account_id}")
        
        return self.accounts[account_id]
    
    def list_accounts(self) -> List[Account]:
        """List all configured accounts"""
        return list(self.accounts.values())
    
    def verify_account(self, account_id: str, instagram_account_id: Optional[str] = None) -> Dict[str, any]:
        """
        Verify account credentials and get account info
        
        Args:
            account_id: Account identifier
            instagram_account_id: Optional Instagram Business Account ID to use
            
        Returns:
            Account information from Instagram API
        """
        client = self.get_client(account_id)
        
        try:
            account_info = client.get_account_info(instagram_account_id)
            
            logger.info(
                "Account verified",
                account_id=account_id,
                instagram_id=account_info.get("id"),
                username=account_info.get("username"),
            )
            
            return account_info
        
        except RetryError as e:
            # Extract the underlying exception from RetryError
            error_msg = str(e)
            
            # Try to extract the actual exception from RetryError
            if hasattr(e, 'last_attempt') and e.last_attempt is not None:
                try:
                    underlying_error = e.last_attempt.exception()
                    error_msg = str(underlying_error)
                    
                    # If the underlying error has more details, use those
                    if isinstance(underlying_error, InstagramAPIError):
                        error_code = getattr(underlying_error, 'error_code', None)
                        error_subcode = getattr(underlying_error, 'error_subcode', None)
                        if error_code:
                            error_msg = f"{error_msg} (code: {error_code}, subcode: {error_subcode})"
                except Exception:
                    # If we can't extract the exception, use the RetryError message
                    pass
            
            logger.error(
                "Account verification failed",
                account_id=account_id,
                error=error_msg,
                retry_error=True,
            )
            raise AccountError(f"Account verification failed: {error_msg}")
        except Exception as e:
            error_msg = str(e)
            logger.error(
                "Account verification failed",
                account_id=account_id,
                error=error_msg,
            )
            raise AccountError(f"Account verification failed: {error_msg}")
    
    def verify_all_accounts(self) -> Dict[str, Dict[str, any]]:
        """Verify all accounts and return status"""
        results = {}
        
        for account_id in self.accounts.keys():
            try:
                results[account_id] = {
                    "status": "verified",
                    "info": self.verify_account(account_id),
                }
            except RetryError as e:
                # Extract the underlying exception from RetryError
                error_msg = str(e)
                
                # Try to extract the actual exception from RetryError
                if hasattr(e, 'last_attempt') and e.last_attempt is not None:
                    try:
                        underlying_error = e.last_attempt.exception()
                        error_msg = str(underlying_error)
                        
                        # If the underlying error has more details, use those
                        if isinstance(underlying_error, InstagramAPIError):
                            error_code = getattr(underlying_error, 'error_code', None)
                            if error_code:
                                error_msg = f"{error_msg} (code: {error_code})"
                    except Exception:
                        # If we can't extract the exception, use the RetryError message
                        pass
                
                results[account_id] = {
                    "status": "failed",
                    "error": error_msg,
                }
            except Exception as e:
                results[account_id] = {
                    "status": "failed",
                    "error": str(e),
                }
        
        return results
