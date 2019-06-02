import json

import werkzeug.exceptions
from flask import jsonify, Blueprint, current_app
from redis import Redis

from app import VideoService

bp = Blueprint('api', __name__, url_prefix='/api')

redis_app = Redis()


@bp.route('/health', methods=['GET'])
def health():
    return jsonify(status='ok')


@bp.route('/stats', methods=['GET'])
def stats():
    jstats = redis_app.get('PARKLAPSE_STATS')
    if not jstats:
        raise werkzeug.exceptions.BadRequest('No stats yet')
    return jsonify(json.loads(jstats))


@bp.route('/hello', methods=['POST'])
def hello():
    from app.tasks import hello_task
    res = hello_task.delay().get()
    return jsonify(result=repr(res))


@bp.route('/generate', methods=['POST'])
def generate():
    video_service = VideoService(current_app.config['RAW_CAPTURE_PATH'],
                                 current_app.config['TIMELAPSE_PATH'],
                                 current_app.config['TMP_PATH'])

    video_service.check_timelapses()
    return jsonify(status='ok')
