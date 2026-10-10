from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import pytest


def test_month_end_uses_shanghai_and_leap_year():
    from server.core import is_month_end
    assert is_month_end(datetime(2024, 2, 29, 13, 17, tzinfo=timezone.utc))
    assert not is_month_end(datetime(2024, 2, 28, 13, 17, tzinfo=timezone.utc))
    assert is_month_end(datetime(2025, 2, 28, 13, 17, tzinfo=timezone.utc))
    assert is_month_end(datetime(2026, 4, 30, 13, 17, tzinfo=timezone.utc))
    assert not is_month_end(datetime(2026, 4, 30, 18, 0, tzinfo=timezone.utc))


def test_concurrent_reservations_never_exceed_budget(tmp_path):
    from server.core import Store
    store = Store(tmp_path)
    store.create_budget("batch", 1)
    barrier = Barrier(2)

    def reserve():
        barrier.wait()
        try:
            store.reserve("batch", 0.7)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: reserve(), range(2))) == [False, True]
    assert store.budget("batch")["reserved"] == pytest.approx(0.7)


def test_quality_failure_cannot_win_by_speed():
    from server.core import rank_results
    rows = [{"candidate": "fast", "quality": 0, "duration": 1, "cost": 0.1, "status": "failed"},
            {"candidate": "accurate", "quality": 1, "duration": 4, "cost": 0.4, "status": "completed"}]
    r = rank_results(rows)
    assert r[0]["candidate"] == "accurate"
    assert r[0]["eligible"] is True
    assert r[1]["eligible"] is False

