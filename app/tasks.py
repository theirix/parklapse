from celery.utils.log import get_task_logger

from app import VideoService, init_video_service
from app.celery import celery_app

video_service = VideoService()

init_video_service(video_service, celery_app.conf)


@celery_app.task
def hello_task():
    return 'hello world'


@celery_app.task(ignore_result=True)
def check_timelapse_task():
    logger = get_task_logger(check_timelapse_task.name)
    logger.info("Called check_timelapse_task")

    video_service.check_timelapses(celery_app.conf['READ_ONLY'], False)


@celery_app.task(ignore_result=True)
def archive_task():
    logger = get_task_logger(archive_task.name)
    logger.info("Called archive_task")

    video_service.archive(celery_app.conf['READ_ONLY'])
