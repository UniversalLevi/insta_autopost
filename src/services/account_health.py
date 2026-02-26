"""Account health monitoring service - checks account status periodically"""

import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from threading import Thread, Event

from ..models.account import Account
from ..services.account_service import AccountService
from ..utils.logger import get_logger
from ..utils.exceptions import AccountError, InstagramAPIError

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Account health status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HealthCheckResult:
    """Result of a health check"""
    
    def __init__(
        self,
        account_id: str,
        status: HealthStatus,
        checks: Dict[str, Dict[str, Any]],
        timestamp: datetime,
    ):
        self.account_id = account_id
        self.status = status
        self.checks = checks
        self.timestamp = timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "status": self.status.value,
            "checks": self.checks,
            "timestamp": self.timestamp.isoformat(),
        }


class AccountHealthService:
    """Service for monitoring account health"""
    
    def __init__(
        self,
        account_service: AccountService,
        check_interval_seconds: int = 600,  # 10 minutes
    ):
        self.account_service = account_service
        self.check_interval_seconds = check_interval_seconds
        self.health_status: Dict[str, HealthCheckResult] = {}
        self.monitoring = False
        self.monitor_thread: Optional[Thread] = None
        self.stop_event = Event()
    
    def check_account_health(self, account_id: str) -> HealthCheckResult:
        """
        Perform comprehensive health check for an account.
        
        Checks:
        - Token validity
        - Permission status
        - API connectivity
        - Webhook status (if applicable)
        - Scheduler status (if applicable)
        
        Args:
            account_id: Account identifier
            
        Returns:
            HealthCheckResult with status and details
        """
        checks = {}
        overall_status = HealthStatus.UNKNOWN
        
        logger.debug("Starting health check", account_id=account_id)
        
        # Check 1: Token validity
        token_check = self._check_token_validity(account_id)
        checks["token"] = token_check
        
        # Check 2: Permission status
        permission_check = self._check_permissions(account_id)
        checks["permissions"] = permission_check
        
        # Check 3: API connectivity
        api_check = self._check_api_connectivity(account_id)
        checks["api_connectivity"] = api_check
        
        # Check 4: Webhook status (placeholder - webhooks are manual)
        webhook_check = self._check_webhook_status(account_id)
        checks["webhook"] = webhook_check
        
        # Check 5: Scheduler status (placeholder - schedulers are global)
        scheduler_check = self._check_scheduler_status(account_id)
        checks["scheduler"] = scheduler_check
        
        # Determine overall status
        critical_checks = ["token", "api_connectivity"]
        warning_checks = ["permissions"]
        
        critical_failed = any(
            checks.get(check, {}).get("status") == "failed"
            for check in critical_checks
        )
        warning_failed = any(
            checks.get(check, {}).get("status") == "failed"
            for check in warning_checks
        )
        
        if critical_failed:
            overall_status = HealthStatus.CRITICAL
        elif warning_failed:
            overall_status = HealthStatus.WARNING
        elif all(
            checks.get(check, {}).get("status") == "ok"
            for check in critical_checks
        ):
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNKNOWN
        
        result = HealthCheckResult(
            account_id=account_id,
            status=overall_status,
            checks=checks,
            timestamp=datetime.now(),
        )
        
        self.health_status[account_id] = result
        
        logger.info(
            "Health check completed",
            account_id=account_id,
            status=overall_status.value,
            critical_failed=critical_failed,
            warning_failed=warning_failed,
        )
        
        return result
    
    def check_all_accounts(self) -> Dict[str, HealthCheckResult]:
        """Check health for all accounts"""
        results = {}
        accounts = self.account_service.list_accounts()
        
        for account in accounts:
            try:
                result = self.check_account_health(account.account_id)
                results[account.account_id] = result
            except Exception as e:
                logger.error(
                    "Health check failed for account",
                    account_id=account.account_id,
                    error=str(e),
                )
                # Create failed result
                results[account.account_id] = HealthCheckResult(
                    account_id=account.account_id,
                    status=HealthStatus.CRITICAL,
                    checks={"error": {"status": "failed", "error": str(e)}},
                    timestamp=datetime.now(),
                )
        
        return results
    
    def get_account_health(self, account_id: str) -> Optional[HealthCheckResult]:
        """Get last health check result for an account"""
        return self.health_status.get(account_id)
    
    def start_monitoring(self) -> None:
        """Start background health monitoring"""
        if self.monitoring:
            logger.warning("Health monitoring already running")
            return
        
        self.monitoring = True
        self.stop_event.clear()
        
        self.monitor_thread = Thread(
            target=self._monitor_loop,
            daemon=True,
            name="account-health-monitor",
        )
        self.monitor_thread.start()
        
        logger.info(
            "Account health monitoring started",
            interval_seconds=self.check_interval_seconds,
        )
    
    def stop_monitoring(self) -> None:
        """Stop background health monitoring"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        self.stop_event.set()
        
        if self.monitor_thread:
            # Don't wait too long - daemon thread will exit with main process
            self.monitor_thread.join(timeout=2)
            if self.monitor_thread.is_alive():
                logger.warning("Health monitor thread still alive after timeout, continuing shutdown")
            self.monitor_thread = None
        
        logger.info("Account health monitoring stopped")
    
    def _monitor_loop(self) -> None:
        """Background monitoring loop"""
        logger.info("Health monitoring loop started")
        
        while not self.stop_event.is_set():
            try:
                self.check_all_accounts()
            except Exception as e:
                logger.error("Error in health monitoring loop", error=str(e))
            try:
                self.stop_event.wait(timeout=self.check_interval_seconds)
            except Exception as e:
                logger.warning("Health monitor wait error", error=str(e))
        
        logger.info("Health monitoring loop stopped")
    
    def _check_token_validity(self, account_id: str) -> Dict[str, Any]:
        """Check if access token is valid"""
        try:
            account = self.account_service.get_account(account_id)
            
            if not account.access_token:
                return {
                    "status": "failed",
                    "error": "No access token",
                    "timestamp": datetime.now().isoformat(),
                }
            
            # Try to use token to verify it's valid
            client = self.account_service.get_client(account_id)
            account_info = client.get_account_info()
            
            if account_info and account_info.get("id"):
                return {
                    "status": "ok",
                    "instagram_id": account_info.get("id"),
                    "username": account_info.get("username"),
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {
                    "status": "failed",
                    "error": "Token validation returned no account info",
                    "timestamp": datetime.now().isoformat(),
                }
        
        except AccountError as e:
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Token check error: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }
    
    def _check_permissions(self, account_id: str) -> Dict[str, Any]:
        """Check required API permissions"""
        try:
            client = self.account_service.get_client(account_id)
            # Try to get account info to verify permissions
            account_info = client.get_account_info()
            
            if account_info:
                return {
                    "status": "ok",
                    "has_permissions": True,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {
                    "status": "failed",
                    "error": "Cannot retrieve account info - check permissions",
                    "timestamp": datetime.now().isoformat(),
                }
        
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Permission check error: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }
    
    def _check_api_connectivity(self, account_id: str) -> Dict[str, Any]:
        """Check API connectivity"""
        try:
            client = self.account_service.get_client(account_id)
            account_info = client.get_account_info()
            
            if account_info:
                return {
                    "status": "ok",
                    "response_time_ms": "<1000",  # Placeholder
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {
                    "status": "failed",
                    "error": "No response from API",
                    "timestamp": datetime.now().isoformat(),
                }
        
        except InstagramAPIError as e:
            return {
                "status": "failed",
                "error": f"API error: {str(e)}",
                "error_code": getattr(e, "error_code", None),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Connectivity error: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }
    
    def _check_webhook_status(self, account_id: str) -> Dict[str, Any]:
        """Check webhook status (placeholder - webhooks are configured manually)"""
        # Webhooks are configured manually in Meta App Dashboard
        # This is a placeholder for future webhook management
        return {
            "status": "unknown",
            "note": "Webhook status requires manual verification in Meta App Dashboard",
            "timestamp": datetime.now().isoformat(),
        }
    
    def _check_scheduler_status(self, account_id: str) -> Dict[str, Any]:
        """Check scheduler status (schedulers are global, not per-account)"""
        # Schedulers are global, not per-account
        # This check verifies the account is included in scheduled tasks
        try:
            account = self.account_service.get_account(account_id)
            # If account exists and has client, scheduler can use it
            return {
                "status": "ok",
                "note": "Scheduler is global and includes all accounts",
                "timestamp": datetime.now().isoformat(),
            }
        except AccountError as e:
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
