from unittest.mock import MagicMock

from app.workers import whatsapp_dispatch
from app.workers.celery_app import celery_app


def test_targeted_whatsapp_jobs_use_dedicated_queue_and_expiry(monkeypatch):
    send_task = MagicMock()
    monkeypatch.setattr(whatsapp_dispatch.celery_app, "send_task", send_task)

    whatsapp_dispatch.enqueue_webhook_event("event-a", "org-a")
    whatsapp_dispatch.enqueue_message("message-a", "org-a")
    whatsapp_dispatch.enqueue_message("message-b", "org-a", delay_seconds=90)

    assert send_task.call_count == 3
    assert send_task.call_args_list[0].kwargs == {
        "args": ["event-a", "org-a"],
        "queue": "whatsapp",
        "expires": 90,
    }
    assert send_task.call_args_list[1].kwargs == {
        "args": ["message-a", "org-a"],
        "queue": "whatsapp",
        "expires": 90,
    }
    assert send_task.call_args_list[2].kwargs == {
        "args": ["message-b", "org-a"],
        "queue": "whatsapp",
        "expires": 180,
        "countdown": 90,
    }


def test_recovery_sweep_is_slower_than_fast_path_and_cannot_expire_immediately():
    schedule = celery_app.conf.beat_schedule["process-whatsapp-inbox-outbox"]

    assert schedule["schedule"] == 30.0
    assert schedule["options"] == {"expires": 90, "queue": "whatsapp"}
    assert celery_app.conf.task_routes["app.workers.whatsapp.process_message"] == {
        "queue": "whatsapp"
    }
