import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "engine_client",
    broker=os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)

terrain_celery_app = Celery(
    "terrain_client",
    broker=os.getenv("TERRAIN_CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("TERRAIN_CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
)

celery_app.conf.update(
    task_default_queue=os.getenv("DEFAULT_QUEUE", "import_jobs"),
    task_track_started=True,
    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", "86400")),
)
