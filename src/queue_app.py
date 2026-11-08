import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()
celery_app = Celery("vision", broker=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
celery_app.conf.update(
    worker_concurrency=1, worker_prefetch_multiplier=1,
    task_acks_late=False, task_reject_on_worker_lost=False,
    broker_connection_timeout=3, broker_connection_retry_on_startup=True,
    task_publish_retry=False, task_soft_time_limit=840, task_time_limit=900,
    task_serializer="json", accept_content=["json"], broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3},
)

@celery_app.task(name="vision.execute", max_retries=0)
def execute_task(task_id):
    from .web_app import run_task
    run_task(task_id)


@celery_app.task(name="vision.mark_interrupted")
def mark_interrupted(task_id):
    """Explicit operator action after stopping the worker. Never reruns models."""
    from .web_app import SessionLocal, Task
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task and task.status in {"pending", "running"}:
            for field in ["yolo_status", "vlm_status"]:
                if getattr(task, field) != "success":
                    setattr(task, field, "failed")
            task.status = "partial_success" if "success" in {task.yolo_status, task.vlm_status} else "failed"
            task.error = (task.error or "") + " | WORKER_INTERRUPTED: operator confirmed"
            db.commit()
