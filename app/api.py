import datetime
import os

import bleach
import werkzeug.exceptions
from flask import jsonify, Blueprint, current_app, redirect

from app import video_service, limiter, redis_app
from app.services import StatsService

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
@limiter.exempt
def health():
    """Reports a service health"""
    return jsonify(status='ok', debug=current_app.config.get('DEBUG', False))


@bp.route('/stats', methods=['GET'])
@limiter.limit("1 per second")
def stats():
    """Reports a service stats"""
    stats_dict = StatsService(redis_app).collect_stats(video_service)
    return jsonify(stats_dict)


@bp.route('/hello', methods=['POST'])
@limiter.limit("1 per minute")
def hello():
    """Debug task"""
    from app.tasks import hello_task
    res = hello_task.delay().get()
    return jsonify(result=repr(res))


@bp.route('/timelapses', methods=['GET'])
def timelapses():
    """Returns a list of available hourly and daily timelapses"""
    res = {}
    for file, dt, slot in video_service.provide_timelapse_slots():
        res.setdefault(dt.strftime("%Y%m%d"), {})
        res[dt.strftime("%Y%m%d")].setdefault('slots', []).append(slot)
        res[dt.strftime("%Y%m%d")]['daily'] = False
    for file, dt in video_service.provide_timelapse_daily():
        res.setdefault(dt.strftime("%Y%m%d"), {})
        res[dt.strftime("%Y%m%d")]['daily'] = True
    return jsonify(res)


@bp.route('/timelapses/<string:date>/hourly/<int:slot>', methods=['GET'])
def timelapses_hourly(date, slot):
    """Redirects to a videofile for given hourly timelapse"""
    date_str = bleach.clean(date)
    current_app.logger.info(f"Request timelapses_hourly for date {date_str} slot {slot}")
    try:
        dt = datetime.datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise werkzeug.exceptions.BadRequest("Wrong date passed, should be YYYYMMDD")
    if not slot or slot < 1 or slot > 8:
        raise werkzeug.exceptions.BadRequest("Wrong slot, should be in [1;8]")
    filepath = video_service.get_timelapses_for_slot(dt, slot)
    if not filepath:
        raise werkzeug.exceptions.NotFound("Timelapse not found")
    current_app.logger.info(f"Found timelapse at {filepath}")
    location = '{}/{}'.format(current_app.config['TIMELAPSES_URL_PREFIX'].rstrip('/'),
                              os.path.basename(filepath))
    return redirect(location=location, code=302)


@bp.route('/timelapses/<string:date>/daily', methods=['GET'])
def timelapses_daily(date):
    """Redirects to a videofile for given daily timelapse"""
    date_str = bleach.clean(date)
    current_app.logger.info(f"Request timelapses_daily for date {date_str}")
    try:
        dt = datetime.datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise werkzeug.exceptions.BadRequest("Wrong date passed, should be YYYYMMDD")
    filepath = video_service.get_timelapses_for_date(dt)
    if not filepath:
        raise werkzeug.exceptions.NotFound("Timelapse not found")
    current_app.logger.info(f"Found timelapse at {filepath}")
    location = '{}/{}'.format(current_app.config['TIMELAPSES_URL_PREFIX'].rstrip('/'),
                              os.path.basename(filepath))
    return redirect(location=location, code=302)
