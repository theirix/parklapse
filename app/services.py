import logging


class VideoService:
    logger = logging.getLogger(__name__)

    def __init__(self, storage_directory):
        self.storage_directory = storage_directory
