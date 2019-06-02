from celery import Celery

celery_app = Celery('parklapse',
                    broker='redis://',
                    backend='redis://',
                    include=['app.tasks'])

celery_app.conf.update(
    result_expires=3600,
)

if __name__ == '__main__':
    celery_app.start()
