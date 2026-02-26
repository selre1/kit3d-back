import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "api_client",
    broker=os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//"),
)

celery_app.conf.update(
    task_default_queue=os.getenv("CELERY_QUEUE", "import_jobs"),
)
