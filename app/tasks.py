from celery.utils.log import get_task_logger

from app import video_service
from app.celery import celery_app


@celery_app.task
def hello_task():
    return 'hello world'


@celery_app.task(ignore_result=True)
def timelapse_task():
    logger = get_task_logger(timelapse_task.name)
    logger.info("Called timelapse_task")

    video_service.check_timelapses(celery_app.conf['READ_ONLY'], False)


@celery_app.task(ignore_result=True)
def archive_task():
    logger = get_task_logger(archive_task.name)
    logger.info("Called archive_task")

    video_service.archive(celery_app.conf['READ_ONLY'],
                          celery_app.conf['ENABLE_ARCHIVE_COMPRESSION'])


@celery_app.task(ignore_result=True)
def watchdog_task():
    logger = get_task_logger(watchdog_task.name)
    logger.info("Called watchdog_task")

    video_service.watchdog(celery_app.conf['ENABLE_WATCHDOG_PROCESS'],
                           celery_app.conf['ENABLE_WATCHDOG_CELERY'], )


@celery_app.task(ignore_result=True)
def cleanup_task():
    logger = get_task_logger(cleanup_task.name)
    logger.info("Called cleanup_task")

    video_service.cleanup(celery_app.conf['READ_ONLY'])


@celery_app.task(ignore_result=True, expires=60)
def receive_task():
    logger = get_task_logger(receive_task.name)
    logger.info("Called receive_task")

    task_id = celery_app.current_task.request.id

    video_service.receive(celery_app.conf['RTSP_SOURCE'], task_id)
