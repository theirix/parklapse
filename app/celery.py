from celery import Celery
from celery.signals import worker_process_init
from redis import Redis

from app import Config, video_service, init_video_service

# Celery global instance
celery_app = Celery('parklapse',
                    broker=Config.REDIS_URL,
                    backend=Config.REDIS_URL,
                    include=['app.tasks'])

celery_app.config_from_object(Config)


@worker_process_init.connect
def worker_process_init_handler(**_kwargs):
    """Handler for worker initialization"""
    print('signal: worker process is ready')

    init_video_service(video_service, celery_app.conf)
    redis = Redis.from_url(Config.REDIS_URL)

    video_service.init_app(redis)


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **_kwargs):
    """Handler for whole celery initialization"""
    print('Setup tasks')
    import app.tasks
    sender.add_periodic_task(60.0, app.tasks.timelapse_task.s(), name='timelapse_task',
                             queue='slow')
    sender.add_periodic_task(300.0, app.tasks.archive_task.s(), name='archive_task',
                             queue='slow')
    sender.add_periodic_task(30.0, app.tasks.watchdog_task.s(), name='watchdog_task',
                             queue='fast')
    sender.add_periodic_task(600.0, app.tasks.cleanup_task.s(), name='cleanup_task',
                             queue='slow')
    sender.add_periodic_task(60.0, app.tasks.receive_task.s(), name='receive_task',
                             queue='inf')


if __name__ == '__main__':
    # Celery entry point
    celery_app.start()
