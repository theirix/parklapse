from flask_env import MetaFlaskEnv


class Config(metaclass=MetaFlaskEnv):
    DEBUG = False
    TESTING = False
    SECRET_KEY = 'secret'
    RAW_CAPTURE_PATH = None
    TIMELAPSE_PATH = None
    ARCHIVE_PATH = None
    TMP_PATH = None
    REDIS_URL = 'redis://localhost:6379'
    TIMELAPSES_URL_PREFIX = '/'
    CORS_ORIGIN = None
    READ_ONLY = True
    ENABLE_S3 = False
    BUCKET_NAME = None
    BUCKET_STORAGE_CLASS = 'ONEZONE_IA'
