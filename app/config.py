from flask_env import MetaFlaskEnv


class Config(metaclass=MetaFlaskEnv):
    DEBUG = False
    TESTING = False
    SECRET_KEY = 'secret'
    PHOTO_STORAGE_PATH = None
