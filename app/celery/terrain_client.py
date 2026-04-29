import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

TERRAIN_CELERY_BROKER_URL = os.getenv(
    "TERRAIN_CELERY_BROKER_URL",
    "redis://localhost:6379/1",
)
TERRAIN_CELERY_RESULT_BACKEND = os.getenv(
    "TERRAIN_CELERY_RESULT_BACKEND",
    "redis://localhost:6379/2",
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
