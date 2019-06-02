from .celery import celery_app


@celery_app.task
def hello_task():
    return 'hello world'
