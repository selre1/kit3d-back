import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "api_client",
    broker=os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)

celery_app.conf.update(
    task_default_queue=os.getenv("DEFAULT_QUEUE", "import_jobs"),
    task_track_started=True,
    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", "86400")),
)
