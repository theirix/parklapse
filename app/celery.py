from celery import Celery

from app import Config

celery_app = Celery('parklapse',
                    broker='redis://',
                    backend='redis://',
                    include=['app.tasks'])

celery_app.config_from_object(Config)


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    print('Setup tasks')
    import app.tasks
    sender.add_periodic_task(60.0, app.tasks.check_timelapse_task.s(), name='check_timelapse_task')
    sender.add_periodic_task(300.0, app.tasks.archive_task.s(), name='archive_task')


if __name__ == '__main__':
    celery_app.start()
