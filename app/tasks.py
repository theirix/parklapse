import datetime
import json

from celery.utils.log import get_task_logger
from redis import Redis

from app import VideoService
from app.celery import celery_app

redis_app = Redis()
video_service = VideoService(celery_app.conf['RAW_CAPTURE_PATH'],
                             celery_app.conf['TIMELAPSE_PATH'],
                             celery_app.conf['TMP_PATH'], )


@celery_app.task
def hello_task():
    return 'hello world'


@celery_app.task(ignore_result=True)
def collect_stats_task():
    logger = get_task_logger(collect_stats_task.name)

    logger.info("Called collect_stats_task")
    stats = dict()
    stats['alive'] = True
    stats['stats_at'] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    try:
        stats['raw_count'] = video_service.raw_count()
        if video_service.raw_last_at():
            stats['raw_last_at'] = video_service.raw_last_at().replace(microsecond=0).isoformat()
        stats['timelapses_success_count'] = video_service.timelapses_count()
        stats['timelapses_error_count'] = video_service.timelapses_error_count()
        stats['timelapse_last_file'] = video_service.timelapse_last_file()
        if video_service.timelapse_last_at():
            stats['timelapse_last_at'] = video_service.timelapse_last_at().isoformat()
    except Exception as e:
        logger.error(e)
        stats['error'] = str(e)

    stats = {k: v for k, v in stats.items() if v is not None}
    redis_app.set('parklapse.stats', json.dumps(stats))


@celery_app.task(ignore_result=True)
def check_timelapse_task():
    logger = get_task_logger(check_timelapse_task.name)
    logger.info("Called check_timelapse_task")

    video_service.check_timelapses(False, False)
