"""Account health monitoring system"""

from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Account health status levels"""
    EXCELLENT = "excellent"  # 0.9-1.0
    GOOD = "good"  # 0.7-0.9
    FAIR = "fair"  # 0.5-0.7
    POOR = "poor"  # 0.3-0.5
    CRITICAL = "critical"  # 0.0-0.3


class HealthMetric:
    """Represents a health metric"""
    
    def __init__(
        self,
        name: str,
        value: float,
        weight: float = 1.0,
        timestamp: Optional[datetime] = None,
    ):
        self.name = name
        self.value = value  # 0.0-1.0
        self.weight = weight
        self.timestamp = timestamp or datetime.utcnow()


class HealthMonitor:
    """
    Monitors account health based on various metrics.
    
    Health factors:
    - API error rates
    - Rate limit hits
    - Action success rates
    - Account response times
    - Unusual patterns
    - Token validity
    """
    
    def __init__(self):
        self.account_metrics: Dict[str, List[HealthMetric]] = {}
        self.account_health_scores: Dict[str, float] = {}
        self.account_statuses: Dict[str, HealthStatus] = {}
    
    def record_metric(
        self,
        account_id: str,
        metric_name: str,
        value: float,
        weight: float = 1.0,
    ):
        """
        Record a health metric for an account
        
        Args:
            account_id: Account identifier
            metric_name: Name of the metric
            value: Metric value (0.0-1.0, where 1.0 is healthy)
            weight: Weight of this metric in health calculation
        """
        if account_id not in self.account_metrics:
            self.account_metrics[account_id] = []
        
        metric = HealthMetric(
            name=metric_name,
            value=max(0.0, min(1.0, value)),  # Clamp to 0.0-1.0
            weight=weight,
        )
        
        self.account_metrics[account_id].append(metric)
        
        # Keep only recent metrics (last 24 hours)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.account_metrics[account_id] = [
            m for m in self.account_metrics[account_id]
            if m.timestamp >= cutoff
        ]
        
        # Recalculate health score
        self._calculate_health_score(account_id)
    
    def record_success(self, account_id: str, action_type: str):
        """Record a successful action"""
        self.record_metric(
            account_id=account_id,
            metric_name=f"{action_type}_success_rate",
            value=1.0,
            weight=0.5,
        )
    
    def record_failure(self, account_id: str, action_type: str, error_type: Optional[str] = None):
        """Record a failed action"""
        self.record_metric(
            account_id=account_id,
            metric_name=f"{action_type}_success_rate",
            value=0.0,
            weight=0.5,
        )
        
        # Track specific error types
        if error_type:
            self.record_metric(
                account_id=account_id,
                metric_name=f"error_{error_type}",
                value=0.0,
                weight=1.0,
            )
    
    def record_rate_limit(self, account_id: str):
        """Record a rate limit hit"""
        self.record_metric(
            account_id=account_id,
            metric_name="rate_limit_hits",
            value=0.3,  # Significant penalty
            weight=1.5,
        )
    
    def _calculate_health_score(self, account_id: str) -> float:
        """Calculate overall health score for an account"""
        if account_id not in self.account_metrics or not self.account_metrics[account_id]:
            return 1.0  # Default to healthy if no metrics
        
        metrics = self.account_metrics[account_id]
        
        # Weighted average of all metrics
        total_weight = sum(m.weight for m in metrics)
        if total_weight == 0:
            return 1.0
        
        weighted_sum = sum(m.value * m.weight for m in metrics)
        score = weighted_sum / total_weight
        
        self.account_health_scores[account_id] = score
        
        # Update status
        if score >= 0.9:
            status = HealthStatus.EXCELLENT
        elif score >= 0.7:
            status = HealthStatus.GOOD
        elif score >= 0.5:
            status = HealthStatus.FAIR
        elif score >= 0.3:
            status = HealthStatus.POOR
        else:
            status = HealthStatus.CRITICAL
        
        self.account_statuses[account_id] = status
        
        logger.debug(
            "Health score calculated",
            account_id=account_id,
            score=round(score, 3),
            status=status.value,
            metric_count=len(metrics),
        )
        
        return score
    
    def get_health_score(self, account_id: str) -> float:
        """Get current health score for an account"""
        if account_id not in self.account_health_scores:
            return 1.0  # Default to healthy
        return self.account_health_scores[account_id]
    
    def get_health_status(self, account_id: str) -> HealthStatus:
        """Get current health status for an account"""
        if account_id not in self.account_statuses:
            return HealthStatus.GOOD  # Default
        return self.account_statuses[account_id]
    
    def is_healthy(self, account_id: str, min_score: float = 0.5) -> bool:
        """Check if account is healthy enough to continue automation"""
        score = self.get_health_score(account_id)
        return score >= min_score
    
    def get_metrics_summary(self, account_id: str) -> Dict[str, Any]:
        """Get summary of health metrics for an account"""
        if account_id not in self.account_metrics:
            return {
                "account_id": account_id,
                "health_score": 1.0,
                "status": HealthStatus.GOOD.value,
                "metrics": {},
            }
        
        metrics = self.account_metrics[account_id]
        
        # Aggregate metrics by name
        metric_aggregates = {}
        for metric in metrics:
            if metric.name not in metric_aggregates:
                metric_aggregates[metric.name] = {
                    "count": 0,
                    "total_value": 0.0,
                    "total_weight": 0.0,
                }
            
            agg = metric_aggregates[metric.name]
            agg["count"] += 1
            agg["total_value"] += metric.value * metric.weight
            agg["total_weight"] += metric.weight
        
        # Calculate averages
        metric_averages = {}
        for name, agg in metric_aggregates.items():
            if agg["total_weight"] > 0:
                metric_averages[name] = agg["total_value"] / agg["total_weight"]
            else:
                metric_averages[name] = agg["total_value"] / max(1, agg["count"])
        
        return {
            "account_id": account_id,
            "health_score": round(self.get_health_score(account_id), 3),
            "status": self.get_health_status(account_id).value,
            "metrics": metric_averages,
            "metric_count": len(metrics),
        }
