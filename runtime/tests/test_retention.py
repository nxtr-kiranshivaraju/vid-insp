"""Daily retention job deletes observations older than the configured cutoff."""

from __future__ import annotations

from datetime import timedelta

from runtime.observability.retention import RetentionJob


async def test_run_once_deletes_only_old_rows(fake_pool, _frozen_time):
    # Seed 100 daily observations stretching from 99 days ago to today.
    for d in range(100):
        ts = _frozen_time.now - timedelta(days=99 - d)
        await fake_pool.execute(
            "INSERT INTO observations "
            "(deployment_id, camera_id, question_id, timestamp, answer, confidence, is_gap) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            "dep_x", "cam_a", "q_a", ts, None, 0.9, False,
        )
    assert len(fake_pool.observations) == 100

    job = RetentionJob(pool=fake_pool, retention_days=90, interval_s=0)
    deleted = await job.run_once()
    assert deleted == 9  # rows older than 90 days: days 99..91 (9 rows)
    assert len(fake_pool.observations) == 91


async def test_zero_deletes_when_all_recent(fake_pool, _frozen_time):
    for d in range(5):
        ts = _frozen_time.now - timedelta(days=d)
        await fake_pool.execute(
            "INSERT INTO observations "
            "(deployment_id, camera_id, question_id, timestamp, answer, confidence, is_gap) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            "dep_x", "cam_a", "q_a", ts, None, 0.9, False,
        )
    job = RetentionJob(pool=fake_pool, retention_days=90)
    deleted = await job.run_once()
    assert deleted == 0
