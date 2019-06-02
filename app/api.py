import json

import werkzeug.exceptions
from flask import jsonify, Blueprint
from redis import Redis

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
