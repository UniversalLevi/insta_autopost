"""
Warm-up data models - Plan, Task, Config.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class WarmupTask:
    """Single task within a day's plan."""
    id: str
    label: str
    manual: bool
    target: int
    category: str = "engage"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "manual": self.manual,
            "target": self.target,
            "category": self.category,
        }


@dataclass
class WarmupPlan:
    """Warm-up plan for an account."""
    account_id: str
    current_day: int = 1
    status: str = "active"
    instagram_id: Optional[str] = None
    start_date: Optional[str] = None
    last_action_time: Optional[str] = None
    risk_score: int = 0
    daily_actions_completed: Dict[str, Any] = field(default_factory=dict)
    completed_tasks: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WarmupPlan":
        return cls(
            account_id=d.get("account_id", ""),
            current_day=int(d.get("current_day", 1)),
            status=d.get("status", "active"),
            instagram_id=d.get("instagram_id"),
            start_date=d.get("start_date"),
            last_action_time=d.get("last_action_time"),
            risk_score=int(d.get("risk_score", 0)),
            daily_actions_completed=d.get("daily_actions_completed") or {},
            completed_tasks=d.get("completed_tasks") or [],
            notes=d.get("notes", ""),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "instagram_id": self.instagram_id or self.account_id,
            "start_date": self.start_date,
            "current_day": self.current_day,
            "status": self.status,
            "last_action_time": self.last_action_time,
            "risk_score": self.risk_score,
            "daily_actions_completed": self.daily_actions_completed,
            "completed_tasks": self.completed_tasks,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class WarmupConfig:
    """Per-account automation config."""
    automation_enabled: bool = True
    target_hashtags: List[str] = field(default_factory=lambda: ["explore", "instagram"])
    schedule_times: List[str] = field(default_factory=lambda: ["09:00", "14:00", "18:00"])

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WarmupConfig":
        return cls(
            automation_enabled=d.get("automation_enabled", True),
            target_hashtags=d.get("target_hashtags") or ["explore", "instagram"],
            schedule_times=d.get("schedule_times") or ["09:00", "14:00", "18:00"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "automation_enabled": self.automation_enabled,
            "target_hashtags": self.target_hashtags,
            "schedule_times": self.schedule_times,
        }
