import datetime
import json

from celery.utils.log import get_task_logger
from redis import Redis

from app import VideoService
from .celery import celery_app

redis_app = Redis()
video_service = VideoService(celery_app.conf['RAW_CAPTURE_PATH'])


@celery_app.task
def hello_task():
    return 'hello world'


@celery_app.task(ignore_result=True)
def collect_stats_task():
    logger = get_task_logger(collect_stats_task.name)

    logger.info("Called collect_stats_task")
    stats = dict()
    stats['alive'] = True
    stats['last'] = datetime.datetime.now().replace(microsecond=0).isoformat()
    try:
        stats['raw_count'] = video_service.raw_count()
        stats['raw_last_at'] = video_service.raw_last_at().replace(microsecond=0).isoformat()
    except Exception as e:
        logger.error(e)
        stats['error'] = str(e)

    stats = {k: v for k, v in stats.items() if v is not None}
    redis_app.set('PARKLAPSE_STATS', json.dumps(stats))
