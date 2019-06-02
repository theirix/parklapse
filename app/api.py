from flask import jsonify, Blueprint

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/health', methods=['GET'])
def health():
    return jsonify(status='ok')
