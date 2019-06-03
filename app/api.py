import datetime
import json
import os

import bleach
import werkzeug.exceptions
from flask import jsonify, Blueprint, current_app, request, redirect

from app import redis_app, video_service

bp = Blueprint('api', __name__, url_prefix='/api')


def str_to_bool(value: str) -> bool:
    """Deduce boolean value from string.
    Credits: flask-restful"""
    if not value:
        raise ValueError("boolean type must be non-null")
    value = value.lower()
    if value in ('true', 'yes', '1',):
        return True
    if value in ('false', 'no', '0',):
        return False
    raise ValueError("Invalid literal for boolean(): {0}".format(value))


@bp.route('/health', methods=['GET'])
def health():
    return jsonify(status='ok', debug=current_app.config.get('DEBUG', False))


@bp.route('/stats', methods=['GET'])
def stats():
    jstats = redis_app.get('parklapse.stats')
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
    raise werkzeug.exceptions.Unauthorized()
    preview = str_to_bool(request.args.get('preview', type=str, default='False'))
    random_failure = str_to_bool(request.args.get('random_failure', type=str, default='False'))
    video_service.check_timelapses(preview, random_failure)
    return jsonify(status='ok')


@bp.route('/timelapses', methods=['GET'])
def timelapses():
    res = {}
    for file, dt, slot in video_service.provide_timelapses():
        res.setdefault(dt.strftime("%Y%m%d"), []).append(slot)
    return jsonify(res)


@bp.route('/timelapses/<string:date>/hourly/<int:slot>', methods=['GET'])
def timelapses_hourly(date, slot):
    date_str = bleach.clean(date)
    current_app.logger.info(f"Request timelapses_hourly for date {date_str} slot {slot}")
    try:
        dt = datetime.datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise werkzeug.exceptions.BadRequest("Wrong date passed, should be YYYYMMDD")
    if not slot or slot < 1 or slot > 8:
        raise werkzeug.exceptions.BadRequest("Wrong slot, should be in [1;8]")
    filepath = video_service.slot_to_timelapse(dt, slot)
    if not filepath:
        raise werkzeug.exceptions.NotFound("Timelapse not found")
    current_app.logger.info(f"Found timelapse at {filepath}")
    location = '{}/{}'.format(current_app.config['TIMELAPSES_URL_PREFIX'].rstrip('/'),
                              os.path.basename(filepath))
    return redirect(location=location, code=302)
