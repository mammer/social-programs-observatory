"""Access control shared by every blueprint."""
from functools import wraps

from flask import jsonify, session


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if "user" not in session:
                return jsonify(error="login_required"), 401
            if role and session.get("role") != role:
                return jsonify(error="forbidden"), 403
            return fn(*a, **kw)
        return wrapper
    return deco
