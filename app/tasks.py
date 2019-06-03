from celery.utils.log import get_task_logger

from app import VideoService
from app.celery import celery_app

video_service = VideoService(celery_app.conf['RAW_CAPTURE_PATH'],
                             celery_app.conf['TIMELAPSE_PATH'],
                             celery_app.conf['TMP_PATH'], )


@celery_app.task
def hello_task():
    return 'hello world'


@celery_app.task(ignore_result=True)
def check_timelapse_task():
    logger = get_task_logger(check_timelapse_task.name)
    logger.info("Called check_timelapse_task")

    video_service.check_timelapses(celery_app.conf['READ_ONLY'], False)
