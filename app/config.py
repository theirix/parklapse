from flask_env import MetaFlaskEnv


class Config(metaclass=MetaFlaskEnv):
    DEBUG = False
    TESTING = False
    SECRET_KEY = 'secret'
    RAW_CAPTURE_PATH = None
    TIMELAPSE_PATH = None
    TMP_PATH = None
    REDIS_URL = 'redis://localhost:6379'
