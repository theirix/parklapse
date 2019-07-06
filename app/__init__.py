import logging
import sys

import flask_cors
import flask_limiter.util
import werkzeug.exceptions
from flask import Flask, jsonify
from flask_redis import FlaskRedis

from app.config import Config
from app.services import VideoService, init_video_service

# Services

redis_app = FlaskRedis()

video_service = VideoService()

limiter = flask_limiter.Limiter(
    key_func=flask_limiter.util.get_remote_address,
    default_limits=["10 per minute"],
)

cors = flask_cors.CORS()

# Error handlers

def errhandler_not_found(_):
    return jsonify({'message': 'Resource not found'}), 404


def errhandler_universal_json(error):
    if isinstance(error, werkzeug.exceptions.HTTPException):
        return jsonify({'message': error.description}), error.code
    return jsonify({'message': str(error)}), 500


def create_app():
    app = Flask(__name__)

    app.config.from_object(Config)

    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

    logging.basicConfig(stream=sys.stdout,
                        format='[%(asctime)s] %(name)s[%(process)d] %(levelname)s -- %(message)s',
                        level='DEBUG')

    app.logger.info("Initializing app")

    redis_app.init_app(app)

    # Register blueprints
    from app.api import bp
    app.register_blueprint(bp)

    # photo service
    if not app.config.get('RAW_CAPTURE_PATH', None):
        raise RuntimeError('No RAW_CAPTURE_PATH specified')
    app.logger.info(f"Raw capture at {app.config['RAW_CAPTURE_PATH']}")

    # exception handlers
    for code in werkzeug.exceptions.default_exceptions:
        app.register_error_handler(code, errhandler_universal_json)

    app.errorhandler(Exception)(errhandler_universal_json)

    app.logger.info("Starting app")

    init_video_service(video_service, app.config)
    video_service.init_app(redis_app)

    limiter.init_app(app)

    cors_resources = {r"/api/health": {"origins": "*"}}
    if app.config['CORS_ORIGIN']:
        cors_resources[r"/api/*"] = {"origins": [s.strip() for s in app.config['CORS_ORIGIN'].split(',')]}
    else:
        cors_resources[r"/api/*"] = {"origins": "*"}
    app.logger.info("CORS configuration: " + repr(cors_resources))
    cors.init_app(app, resources=cors_resources)

    logging.getLogger('flask_cors').level = logging.INFO
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('nose').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    return app
