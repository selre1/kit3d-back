import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

ENGINE_CELERY_BROKER_URL = os.getenv(
    "ENGINE_CELERY_BROKER_URL",
    "amqp://guest:guest@localhost:5672//",
)
ENGINE_CELERY_RESULT_BACKEND = os.getenv(
    "ENGINE_CELERY_RESULT_BACKEND",
    "redis://localhost:6379/0",
)

celery_app = Celery(
    "engine_client",
    broker=ENGINE_CELERY_BROKER_URL,
    backend=ENGINE_CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_track_started=True,
    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", "86400")),
    broker_url=ENGINE_CELERY_BROKER_URL,
    result_backend=ENGINE_CELERY_RESULT_BACKEND,
)
