"""
GigShield AI — Admin Portal (port 5001)
=========================================
Only exposes admin-facing routes.
Run: python run_admin.py
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from flask import Flask, render_template, jsonify
from database import init_db
from ml_model import ensure_models_trained
from routes_admin import admin_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gigshield-admin-2024!")

with app.app_context():
    init_db()
    ensure_models_trained()

# ── Admin blueprint (/admin/*) ────────────────────────────────────
app.register_blueprint(admin_bp)

# ── Landing → redirect to admin login ────────────────────────────
from flask import redirect, url_for

@app.route("/")
def index():
    return redirect(url_for("admin.login"))

@app.errorhandler(404)
def not_found(_): return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e): return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("Admin Portal → http://localhost:5001")
    app.run(debug=True, host="0.0.0.0", port=5001)
