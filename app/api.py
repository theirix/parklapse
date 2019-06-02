from flask import jsonify, Blueprint

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/health', methods=['GET'])
def health():
    return jsonify(status='ok')


@bp.route('/hello', methods=['POST'])
def hello():
    from app.tasks import hello_task
    res = hello_task.delay().get()
    return jsonify(result=repr(res))
