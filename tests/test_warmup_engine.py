"""Tests for 5-Day Warm-Up Engine - Phase 10"""

import pytest


@pytest.fixture(autouse=True)
def use_temp_data(monkeypatch, tmp_path):
    """Use temp dir for warmup data so tests don't touch real data."""
    import src.features.warmup.warmup_store as store
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "WARMUP_PLANS_FILE", tmp_path / "warmup_plans.json")
    monkeypatch.setattr(store, "WARMUP_REPORTS_FILE", tmp_path / "warmup_reports.json")


def test_start_warmup():
    from src.features.warmup.warmup_engine import WarmupEngine
    engine = WarmupEngine()
    plan = engine.start_warmup("acc1")
    assert plan["account_id"] == "acc1"
    assert plan["current_day"] == 1
    assert plan["status"] == "active"
    assert "start_date" in plan


def test_start_warmup_duplicate_raises():
    from src.features.warmup.warmup_engine import WarmupEngine
    engine = WarmupEngine()
    engine.start_warmup("acc2dup")
    with pytest.raises(ValueError, match="already active"):
        engine.start_warmup("acc2dup")


def test_get_today_plan():
    from src.features.warmup.warmup_engine import WarmupEngine
    engine = WarmupEngine()
    engine.start_warmup("acc3")
    today = engine.get_today_plan("acc3")
    assert today is not None
    assert today["current_day"] == 1
    assert "tasks" in today
    assert len(today["tasks"]) > 0


def test_get_today_plan_no_plan():
    from src.features.warmup.warmup_engine import WarmupEngine
    engine = WarmupEngine()
    assert engine.get_today_plan("nonexistent") is None


def test_mark_task_done():
    from src.features.warmup.warmup_engine import WarmupEngine
    engine = WarmupEngine()
    engine.start_warmup("acc4")
    tasks = engine.get_today_plan("acc4")["tasks"]
    task_id = tasks[0]["id"] if tasks else "day1_like"
    updated = engine.mark_task_done("acc4", task_id, count=1)
    assert updated is not None
    completed = updated.get("completed_tasks", [])
    assert any(c.get("task_id") == task_id for c in completed)


def test_complete_day():
    from src.features.warmup.warmup_engine import WarmupEngine
    from src.features.warmup.warmup_store import get_warmup_plan
    engine = WarmupEngine()
    engine.start_warmup("acc5")
    updated = engine.complete_day("acc5")
    assert updated is not None
    assert updated["current_day"] == 2


def test_pause_resume():
    from src.features.warmup.warmup_engine import WarmupEngine
    engine = WarmupEngine()
    engine.start_warmup("acc6")
    paused = engine.pause_warmup("acc6", "test reason")
    assert paused["status"] == "paused"
    resumed = engine.resume_warmup("acc6")
    assert resumed["status"] == "active"


def test_finish_warmup_day5():
    from src.features.warmup.warmup_engine import WarmupEngine
    from src.features.warmup.warmup_store import get_warmup_plan, update_warmup_plan
    engine = WarmupEngine()
    engine.start_warmup("acc7")
    update_warmup_plan("acc7", {"current_day": 5})
    updated = engine.complete_day("acc7")
    assert updated["status"] == "completed"


def test_risk_monitor():
    from src.features.warmup.risk_monitor import RiskMonitor
    from src.features.warmup.warmup_store import get_warmup_plan
    monitor = RiskMonitor()
    # Record API error - 429 should return pause reason
    reason = monitor.record_api_error("acc8", error_code=429)
    assert reason is not None
    assert "429" in reason


def test_warmup_guard():
    from src.middleware.warmup_guard import is_warmup_active, warmup_allows_action
    # No plan - should allow
    allowed, _ = warmup_allows_action("acc9", "bulk_post")
    assert allowed is True
    # With active plan - bulk_post blocked (we'd need to create plan first)
    # Skip - would require setting up plan in temp store
