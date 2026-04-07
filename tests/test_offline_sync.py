from __future__ import annotations

from src.sync.offline_queue import OfflineSyncQueue


def test_queue_enqueue_and_resolve(tmp_path) -> None:
    queue = OfflineSyncQueue(db_path=str(tmp_path / "sync_queue.db"))
    encounter = {
        "id": "enc_test",
        "syndrome": "acute_watery_diarrhea",
        "severity": "severe",
        "district": "Varanasi",
    }

    queue_id = queue.enqueue(encounter, target="idsp", priority=3)
    due = queue.get_due_items()
    assert any(item["id"] == queue_id for item in due)

    queue.mark_resolved(queue_id, {"report_id": "IDSP-123"}, {"server": 1})
    due_after = queue.get_due_items()
    assert not any(item["id"] == queue_id for item in due_after)

    stats = queue.get_queue_stats()
    assert stats["total_items"] >= 1
