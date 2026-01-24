"""Advanced scheduler for task orchestration"""

import time
import random
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import schedule

from ..utils.logger import get_logger

logger = get_logger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledTask:
    """Represents a scheduled task"""
    
    def __init__(
        self,
        task_id: str,
        func: Callable,
        priority: TaskPriority = TaskPriority.NORMAL,
        kwargs: Optional[Dict[str, Any]] = None,
        scheduled_time: Optional[datetime] = None,
        delay_seconds: Optional[float] = None,
        randomize_delay: bool = False,
        max_delay_variance: float = 0.2,
    ):
        self.task_id = task_id
        self.func = func
        self.priority = priority
        self.kwargs = kwargs or {}
        self.scheduled_time = scheduled_time
        self.delay_seconds = delay_seconds
        self.randomize_delay = randomize_delay
        self.max_delay_variance = max_delay_variance
        self.status = TaskStatus.PENDING
        self.created_at = datetime.utcnow()
        self.executed_at: Optional[datetime] = None
        self.error: Optional[str] = None
    
    def get_execution_time(self) -> datetime:
        """Calculate the actual execution time with randomization"""
        if self.scheduled_time:
            base_time = self.scheduled_time
        elif self.delay_seconds:
            base_time = datetime.utcnow() + timedelta(seconds=self.delay_seconds)
        else:
            base_time = datetime.utcnow()
        
        if self.randomize_delay:
            variance = self.max_delay_variance
            delay_multiplier = random.uniform(1 - variance, 1 + variance)
            if self.delay_seconds:
                adjusted_delay = self.delay_seconds * delay_multiplier
                base_time = datetime.utcnow() + timedelta(seconds=adjusted_delay)
            else:
                # Randomize scheduled time slightly
                random_seconds = random.uniform(-300, 300)  # ±5 minutes
                base_time += timedelta(seconds=random_seconds)
        
        return base_time


class AdvancedScheduler:
    """
    Advanced scheduler with priority queuing, randomization, and task management.
    
    Features:
    - Priority-based task execution
    - Randomization for human-like behavior
    - Task persistence (can be extended to disk)
    - Flexible scheduling (cron-like, intervals, one-time)
    - Task cancellation and status tracking
    """
    
    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.task_queue: List[ScheduledTask] = []
        self.running_tasks: Dict[str, ScheduledTask] = {}
        self.completed_tasks: List[ScheduledTask] = []
        self.failed_tasks: List[ScheduledTask] = []
        self._running = False
    
    def schedule_task(
        self,
        task_id: str,
        func: Callable,
        priority: TaskPriority = TaskPriority.NORMAL,
        kwargs: Optional[Dict[str, Any]] = None,
        scheduled_time: Optional[datetime] = None,
        delay_seconds: Optional[float] = None,
        randomize_delay: bool = False,
        max_delay_variance: float = 0.2,
    ) -> str:
        """
        Schedule a task for execution
        
        Args:
            task_id: Unique identifier for the task
            func: Function to execute
            priority: Task priority
            kwargs: Keyword arguments to pass to function
            scheduled_time: Specific time to execute
            delay_seconds: Delay in seconds from now
            randomize_delay: Add randomization to delay
            max_delay_variance: Maximum variance percentage (0.0-1.0)
            
        Returns:
            Task ID
        """
        if task_id in self.tasks:
            logger.warning("Task ID already exists, updating", task_id=task_id)
        
        task = ScheduledTask(
            task_id=task_id,
            func=func,
            priority=priority,
            kwargs=kwargs,
            scheduled_time=scheduled_time,
            delay_seconds=delay_seconds,
            randomize_delay=randomize_delay,
            max_delay_variance=max_delay_variance,
        )
        
        self.tasks[task_id] = task
        task.status = TaskStatus.SCHEDULED
        
        # Add to queue (sorted by priority and execution time)
        self._enqueue_task(task)
        
        logger.info(
            "Task scheduled",
            task_id=task_id,
            priority=priority.value,
            scheduled_time=task.get_execution_time().isoformat() if scheduled_time else None,
            delay_seconds=delay_seconds,
        )
        
        return task_id
    
    def _enqueue_task(self, task: ScheduledTask):
        """Add task to priority queue"""
        self.task_queue.append(task)
        # Sort by priority (enum order) then by execution time
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.NORMAL: 2,
            TaskPriority.LOW: 3,
            TaskPriority.BACKGROUND: 4,
        }
        self.task_queue.sort(
            key=lambda t: (
                priority_order.get(t.priority, 99),
                t.get_execution_time(),
            )
        )
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status in [TaskStatus.PENDING, TaskStatus.SCHEDULED]:
                task.status = TaskStatus.CANCELLED
                if task in self.task_queue:
                    self.task_queue.remove(task)
                logger.info("Task cancelled", task_id=task_id)
                return True
        
        return False
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a task"""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        return {
            "task_id": task_id,
            "status": task.status.value,
            "priority": task.priority.value,
            "created_at": task.created_at.isoformat(),
            "executed_at": task.executed_at.isoformat() if task.executed_at else None,
            "error": task.error,
        }
    
    def execute_pending_tasks(self) -> Dict[str, Any]:
        """Execute all pending tasks that are due"""
        results = {
            "executed": 0,
            "failed": 0,
            "skipped": 0,
        }
        
        now = datetime.utcnow()
        tasks_to_execute = []
        
        # Find tasks that are due
        for task in self.task_queue[:]:
            if task.status != TaskStatus.SCHEDULED:
                continue
            
            execution_time = task.get_execution_time()
            if execution_time <= now:
                tasks_to_execute.append(task)
                self.task_queue.remove(task)
        
        # Execute tasks (in priority order)
        for task in tasks_to_execute:
            try:
                task.status = TaskStatus.RUNNING
                self.running_tasks[task.task_id] = task
                
                logger.debug(
                    "Executing scheduled task",
                    task_id=task.task_id,
                    priority=task.priority.value,
                )
                
                # Execute the function
                result = task.func(**task.kwargs)
                
                task.status = TaskStatus.COMPLETED
                task.executed_at = datetime.utcnow()
                self.completed_tasks.append(task)
                results["executed"] += 1
                
                logger.info(
                    "Task completed",
                    task_id=task.task_id,
                    execution_time=(task.executed_at - task.created_at).total_seconds(),
                )
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.executed_at = datetime.utcnow()
                task.error = str(e)
                self.failed_tasks.append(task)
                results["failed"] += 1
                
                logger.error(
                    "Task failed",
                    task_id=task.task_id,
                    error=str(e),
                    exc_info=True,
                )
            
            finally:
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]
        
        return results
    
    def schedule_daily(
        self,
        task_id: str,
        func: Callable,
        time_str: str,
        randomize_minutes: int = 0,
        priority: TaskPriority = TaskPriority.NORMAL,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Schedule a task to run daily at a specific time
        
        Args:
            task_id: Unique task identifier
            func: Function to execute
            time_str: Time in "HH:MM" format
            randomize_minutes: Randomize execution time by ±N minutes
            priority: Task priority
            kwargs: Function arguments
        """
        hour, minute = map(int, time_str.split(":"))
        
        def daily_wrapper():
            # Reschedule for next day
            next_run = datetime.utcnow().replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= datetime.utcnow():
                next_run += timedelta(days=1)
            
            # Add randomization
            if randomize_minutes > 0:
                random_minutes = random.randint(-randomize_minutes, randomize_minutes)
                next_run += timedelta(minutes=random_minutes)
            
            # Execute
            func(**(kwargs or {}))
            
            # Schedule next occurrence
            self.schedule_daily(task_id, func, time_str, randomize_minutes, priority, kwargs)
        
        # Schedule first execution
        next_run = datetime.utcnow().replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= datetime.utcnow():
            next_run += timedelta(days=1)
        
        if randomize_minutes > 0:
            random_minutes = random.randint(-randomize_minutes, randomize_minutes)
            next_run += timedelta(minutes=random_minutes)
        
        return self.schedule_task(
            task_id=task_id,
            func=daily_wrapper,
            priority=priority,
            scheduled_time=next_run,
            randomize_delay=False,  # Already randomized
        )
    
    def schedule_interval(
        self,
        task_id: str,
        func: Callable,
        interval_seconds: float,
        randomize: bool = True,
        max_variance: float = 0.2,
        priority: TaskPriority = TaskPriority.NORMAL,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Schedule a task to run at regular intervals
        
        Args:
            task_id: Unique task identifier
            func: Function to execute
            interval_seconds: Interval between executions
            randomize: Add randomization to intervals
            max_variance: Maximum variance percentage
            priority: Task priority
            kwargs: Function arguments
        """
        def interval_wrapper():
            # Execute
            func(**(kwargs or {}))
            
            # Schedule next execution
            self.schedule_interval(
                task_id=task_id,
                func=func,
                interval_seconds=interval_seconds,
                randomize=randomize,
                max_variance=max_variance,
                priority=priority,
                kwargs=kwargs,
            )
        
        return self.schedule_task(
            task_id=task_id,
            func=interval_wrapper,
            priority=priority,
            delay_seconds=interval_seconds,
            randomize_delay=randomize,
            max_delay_variance=max_variance,
        )
    
    def run_loop(self, check_interval: int = 10):
        """
        Run the scheduler loop
        
        Args:
            check_interval: Seconds between checking for due tasks
        """
        self._running = True
        logger.info("Scheduler loop started", check_interval=check_interval)
        
        while self._running:
            try:
                results = self.execute_pending_tasks()
                if results["executed"] > 0 or results["failed"] > 0:
                    logger.debug(
                        "Scheduler execution cycle",
                        executed=results["executed"],
                        failed=results["failed"],
                    )
            except Exception as e:
                logger.error("Error in scheduler loop", error=str(e), exc_info=True)
            
            time.sleep(check_interval)
    
    def stop(self):
        """Stop the scheduler loop"""
        self._running = False
        logger.info("Scheduler loop stopped")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        return {
            "total_tasks": len(self.tasks),
            "pending": len(self.task_queue),
            "running": len(self.running_tasks),
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
            "cancelled": sum(1 for t in self.tasks.values() if t.status == TaskStatus.CANCELLED),
        }
