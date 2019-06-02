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
    from .tasks import collect_stats_task
    sender.add_periodic_task(30.0, collect_stats_task.s(), name='collect_stats')


if __name__ == '__main__':
    celery_app.start()
