"""
GigShield AI — auth.py
========================
Shared decorators and session helpers for user/admin access control.
"""

from functools import wraps
from flask import session, redirect, url_for, jsonify, request


def user_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "user":
            if request.is_json or request.path.startswith("/user/claim"):
                return jsonify({"error": "Access Denied"}), 403
            return redirect(url_for("user.login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            if request.is_json:
                return jsonify({"error": "Access Denied"}), 403
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return wrapper
