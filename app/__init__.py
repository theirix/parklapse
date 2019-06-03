import logging
import sys

import werkzeug.exceptions
from flask import Flask, jsonify

from app.api import video_service
from app.config import Config
from app.services import VideoService


def errhandler_not_found(_):
    return jsonify({'message': 'Resource not found'}), 404


def errhandler_universal_json(error):
    if isinstance(error, werkzeug.exceptions.HTTPException):
        return jsonify({'message': error.description}), error.code
    return jsonify({'message': str(error)}), 500


def create_app():
    app = Flask(__name__)

    app.config.from_object(Config)

    logging.basicConfig(stream=sys.stdout,
                        format='[%(asctime)s] %(name)s[%(process)d] %(levelname)s -- %(message)s',
                        level='DEBUG')

    app.logger.info("Initializing app")

    # Register blueprints
    from app.api import bp
    app.register_blueprint(bp)

    # photo service
    if not app.config.get('RAW_CAPTURE_PATH', None):
        raise RuntimeError('No env var specified')

    # exception handlers
    for code in werkzeug.exceptions.default_exceptions:
        app.register_error_handler(code, errhandler_universal_json)

    app.errorhandler(Exception)(errhandler_universal_json)

    app.logger.info("Starting app")

    video_service.init_config(app.config['RAW_CAPTURE_PATH'],
                              app.config['TIMELAPSE_PATH'],
                              app.config['TMP_PATH'])

    return app
