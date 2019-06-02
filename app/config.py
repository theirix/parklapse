from flask_env import MetaFlaskEnv


class Config(metaclass=MetaFlaskEnv):
    DEBUG = False
    TESTING = False
    SECRET_KEY = 'secret'
    RAW_CAPTURE_PATH = None
