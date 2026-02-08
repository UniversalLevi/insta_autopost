"""Tests for 5-Day Warm-Up Engine (new modular warmup)"""

import pytest


@pytest.fixture(autouse=True)
def use_temp_data(monkeypatch, tmp_path):
    """Use temp dir for warmup data so tests don't touch real data."""
    import src.features.warmup.store as store
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "PLANS_FILE", tmp_path / "warmup_plans.json")
    monkeypatch.setattr(store, "CONFIG_FILE", tmp_path / "warmup_automation_config.json")
    monkeypatch.setattr(store, "REPORTS_FILE", tmp_path / "warmup_reports.json")


def test_start_warmup():
    from src.features.warmup.engine import start_warmup
    plan = start_warmup("acc1")
    assert plan["account_id"] == "acc1"
    assert plan["current_day"] == 1
    assert plan["status"] == "active"
    assert "start_date" in plan


def test_start_warmup_duplicate_raises():
    from src.features.warmup.engine import start_warmup
    start_warmup("acc2dup")
    with pytest.raises(ValueError, match="already active"):
        start_warmup("acc2dup")


def test_get_today_plan():
    from src.features.warmup.engine import start_warmup, get_today_plan
    start_warmup("acc3")
    today = get_today_plan("acc3")
    assert today is not None
    assert today["current_day"] == 1
    assert "tasks" in today
    assert len(today["tasks"]) > 0


def test_get_today_plan_no_plan():
    from src.features.warmup.engine import get_today_plan
    assert get_today_plan("nonexistent") is None


def test_mark_task_done():
    from src.features.warmup.engine import start_warmup, get_today_plan, mark_task_done
    start_warmup("acc4")
    tasks = get_today_plan("acc4")["tasks"]
    task_id = tasks[0]["id"] if tasks else "day1_like"
    updated = mark_task_done("acc4", task_id, count=1)
    assert updated is not None
    completed = updated.get("completed_tasks", [])
    assert any(c.get("task_id") == task_id for c in completed)


def test_complete_day():
    from src.features.warmup.engine import start_warmup, complete_day
    start_warmup("acc5")
    updated = complete_day("acc5")
    assert updated is not None
    assert updated["current_day"] == 2


def test_pause_resume():
    from src.features.warmup.engine import start_warmup, pause_warmup, resume_warmup
    start_warmup("acc6")
    paused = pause_warmup("acc6", "test reason")
    assert paused["status"] == "paused"
    resumed = resume_warmup("acc6")
    assert resumed["status"] == "active"


def test_finish_warmup_day5():
    from src.features.warmup.engine import start_warmup, complete_day
    from src.features.warmup.store import update_plan
    start_warmup("acc7")
    update_plan("acc7", {"current_day": 5})
    updated = complete_day("acc7")
    assert updated["status"] == "completed"


def test_warmup_guard():
    from src.middleware.warmup_guard import is_warmup_active, warmup_allows_action
    # No plan - should allow
    allowed, _ = warmup_allows_action("acc9", "bulk_post")
    assert allowed is True
