"""
Phase 4 isolation tests: per-user engines, no shared globals.
All features must work for 3+ test users simultaneously.
"""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def v2_data_dir(tmp_path):
    os.environ["V2_DATA_DIR"] = str(tmp_path)
    yield tmp_path
    if "V2_DATA_DIR" in os.environ:
        del os.environ["V2_DATA_DIR"]


def test_resolve_context_returns_none_for_unknown(v2_data_dir):
    from src_v2.core.account_resolver import resolve_context
    assert resolve_context("user-1", "ig-999") is None


def test_stores_isolated_per_user_instagram(v2_data_dir):
    from src_v2.stores.posts_v2 import append_post, list_posts
    from src_v2.stores.schedules_v2 import append_schedule, list_schedules
    from src_v2.stores.dm_logs_v2 import append_dm_log, list_dm_logs
    append_post("u1", "ig1", {"id": "p1", "caption": "user1"})
    append_post("u2", "ig2", {"id": "p2", "caption": "user2"})
    append_post("u1", "ig1", {"id": "p3", "caption": "user1 again"})
    assert len(list_posts("u1", "ig1")) == 2
    assert len(list_posts("u2", "ig2")) == 1
    assert len(list_posts("u1", "ig2")) == 0
    append_schedule("u1", "ig1", {"id": "s1", "scheduled_time": "2026-01-01T12:00:00"})
    append_schedule("u3", "ig3", {"id": "s2"})
    assert len(list_schedules("u1", "ig1")) == 1
    assert len(list_schedules("u3", "ig3")) == 1
    append_dm_log("u1", "ig1", {"sender_id": "x", "message": "hi"})
    append_dm_log("u2", "ig2", {"sender_id": "y", "message": "hey"})
    assert len(list_dm_logs("u1", "ig1", limit=10)) == 1
    assert len(list_dm_logs("u2", "ig2", limit=10)) == 1


def test_three_users_independent_pipelines(v2_data_dir):
    from src_v2.stores.posts_v2 import append_post, list_posts
    from src_v2.stores.user_limits import set_limits, get_limits
    set_limits("user_a", {"posts_per_day": 5})
    set_limits("user_b", {"posts_per_day": 10})
    set_limits("user_c", {"posts_per_day": 3})
    for i in range(2):
        append_post("user_a", "ig_a", {"id": f"a{i}", "n": i})
    for i in range(4):
        append_post("user_b", "ig_b", {"id": f"b{i}", "n": i})
    append_post("user_c", "ig_c", {"id": "c0", "n": 0})
    assert len(list_posts("user_a", "ig_a")) == 2
    assert len(list_posts("user_b", "ig_b")) == 4
    assert len(list_posts("user_c", "ig_c")) == 1
    assert get_limits("user_a").get("posts_per_day") == 5
    assert get_limits("user_b").get("posts_per_day") == 10
    assert get_limits("user_c").get("posts_per_day") == 3


def test_webhook_routes_to_single_user(v2_data_dir):
    from datetime import datetime
    from src_v2.meta.models import (
        ConnectedAccountV2,
        save_accounts,
        get_account_by_instagram_id,
    )
    try:
        from src_v2.meta.crypto import encrypt_token
        enc = encrypt_token
    except Exception:
        pytest.skip("V2_META_ENC_KEY not set")
    accounts = [
        ConnectedAccountV2(
            id="acc1",
            user_id="owner1",
            page_id="page1",
            instagram_id="ig_biz_1",
            page_token_encrypted=enc("dummy_token_1"),
            expires_at=None,
            status="connected",
            created_at=datetime.utcnow(),
        ),
    ]
    save_accounts(accounts)
    acc = get_account_by_instagram_id("ig_biz_1")
    assert acc is not None
    assert acc.user_id == "owner1"
    assert acc.instagram_id == "ig_biz_1"


def test_locks_isolated_per_key(v2_data_dir):
    from src_v2.core.locks import acquire_lock, lock_key_posting
    with acquire_lock(lock_key_posting("u1", "ig1")):
        pass
    with acquire_lock(lock_key_posting("u2", "ig2")):
        pass
    with acquire_lock(lock_key_posting("u1", "ig1"), timeout_seconds=1):
        pass


def test_failure_simulation_one_user_does_not_clear_other(v2_data_dir):
    from src_v2.stores.posts_v2 import append_post, list_posts
    append_post("good_user", "ig_good", {"id": "1", "status": "ok"})
    append_post("bad_user", "ig_bad", {"id": "2", "status": "ok"})
    assert len(list_posts("good_user", "ig_good")) == 1
    assert len(list_posts("bad_user", "ig_bad")) == 1
    from src_v2.services.posting_service_v2 import PostingServiceV2
    from src_v2.core.user_context import UserContext
    ctx_bad = UserContext(
        user_id="bad_user",
        instagram_id="ig_bad",
        page_id="page_bad",
        page_token="x",
        account_id="acc_bad",
        rate_limits={"posts_per_day": 0},
    )
    svc = PostingServiceV2()
    with pytest.raises(RuntimeError, match="limit"):
        svc.create_post(ctx_bad, "image", "https://example.com/1.jpg", "cap")
    assert len(list_posts("good_user", "ig_good")) == 1
    assert len(list_posts("bad_user", "ig_bad")) == 1
