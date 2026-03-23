import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
TERRAIN_CELERY_BROKER_URL = os.getenv(
    "TERRAIN_CELERY_BROKER_URL",
    "redis://localhost:6379/1",
)
TERRAIN_CELERY_RESULT_BACKEND = os.getenv(
    "TERRAIN_CELERY_RESULT_BACKEND",
    "redis://localhost:6379/2",
)

celery_app = Celery(
    "engine_client",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_track_started=True,
    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", "86400")),
    broker_url=CELERY_BROKER_URL,
    result_backend=CELERY_RESULT_BACKEND,
)

terrain_celery_app = Celery(
    "terrain_client",
    broker=TERRAIN_CELERY_BROKER_URL,
    backend=TERRAIN_CELERY_RESULT_BACKEND,
)

terrain_celery_app.conf.update(
    broker_url=TERRAIN_CELERY_BROKER_URL,
    result_backend=TERRAIN_CELERY_RESULT_BACKEND,
)