"""Proxy manager for per-account proxy routing"""

from typing import Dict, Optional
import requests

from ..models.account import Account
from ..utils.logger import get_logger
from ..utils.exceptions import ProxyError

logger = get_logger(__name__)


class ProxyManager:
    """Manages proxy connections for accounts. Supports per-account proxy or shared default proxy."""

    def __init__(
        self,
        accounts: Dict[str, Account],
        connection_timeout: int = 10,
        max_retries: int = 3,
        verify_ssl: bool = False,
        default_proxy_url: Optional[str] = None,
    ):
        self.accounts = accounts
        self.connection_timeout = connection_timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self.default_proxy_url = default_proxy_url
        self.proxy_cache: Dict[str, str] = {}

    def get_proxy_url(self, account_id: str) -> Optional[str]:
        """
        Get proxy URL for an account. Uses per-account proxy if host/port set, else shared default.
        """
        if account_id not in self.accounts:
            raise ProxyError(f"Account not found: {account_id}")

        account = self.accounts[account_id]

        if not account.proxy.enabled:
            return None

        # Return cached proxy URL if available
        if account_id in self.proxy_cache:
            return self.proxy_cache[account_id]

        # Per-account proxy if host/port set; otherwise shared default
        proxy_url = account.proxy.proxy_url
        if not proxy_url and self.default_proxy_url:
            proxy_url = self.default_proxy_url

        if proxy_url:
            self.proxy_cache[account_id] = proxy_url
            logger.debug(
                "Proxy URL retrieved",
                account_id=account_id,
                proxy_host=account.proxy.host,
            )

        return proxy_url
    
    def verify_proxy(self, account_id: str) -> bool:
        """
        Verify proxy connection for an account
        
        Args:
            account_id: Account identifier
            
        Returns:
            True if proxy is working, False otherwise
        """
        proxy_url = self.get_proxy_url(account_id)
        
        if not proxy_url:
            return True  # No proxy needed
        
        try:
            proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }
            
            # Test connection with a simple request
            response = requests.get(
                "https://httpbin.org/ip",
                proxies=proxies,
                timeout=self.connection_timeout,
                verify=self.verify_ssl,
            )
            
            response.raise_for_status()
            
            logger.info(
                "Proxy verified successfully",
                account_id=account_id,
                proxy_ip=response.json().get("origin"),
            )
            
            return True
        
        except Exception as e:
            logger.error(
                "Proxy verification failed",
                account_id=account_id,
                error=str(e),
            )
            return False
    
    def verify_all_proxies(self) -> Dict[str, bool]:
        """Verify all account proxies"""
        results = {}
        
        for account_id in self.accounts.keys():
            results[account_id] = self.verify_proxy(account_id)
        
        return results
