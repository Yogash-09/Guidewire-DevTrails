"""
GigShield AI — routes_admin.py
================================
Blueprint: prefix /admin
Static credential login → dashboard → worker review
"""

import os
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, jsonify)

from database import (
    admin_stats, get_pending_docs, get_worker_by_id,
    admin_review_doc, get_fraud_log, get_fraud_rings,
    get_suspicious_workers,
)
from ml_model import get_income_chart_data
from auth import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1234")


# ── Login / Logout ────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("role") == "admin":
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["role"] = "admin"
            return redirect(url_for("admin.dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("admin_login.html")


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("role_select"))


# ── Dashboard ─────────────────────────────────────────────────────

@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    stats      = admin_stats()
    pending    = get_pending_docs()
    hours, losses = get_income_chart_data()
    fraud_logs = get_fraud_log(limit=20)
    rings      = get_fraud_rings()
    suspicious = get_suspicious_workers()
    return render_template("admin_dashboard.html",
        stats=stats, pending_docs=pending,
        chart_hours=hours, chart_losses=losses,
        fraud_logs=fraud_logs, fraud_rings=rings,
        suspicious_workers=suspicious,
    )


# ── Worker review ─────────────────────────────────────────────────

@admin_bp.route("/review/<int:worker_id>", methods=["POST"])
@admin_required
def review_worker(worker_id):
    action = request.form.get("action", "")
    note   = request.form.get("note", "").strip()
    if action in ("approved", "rejected"):
        admin_review_doc(worker_id, action, note, reviewer="admin")
        flash(f"Worker #{worker_id} documents {action}.",
              "success" if action == "approved" else "warning")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/worker/<int:worker_id>")
@admin_required
def worker_detail(worker_id):
    w = get_worker_by_id(worker_id)
    if not w:
        flash("Worker not found.", "danger")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin_worker_detail.html", worker=dict(w))
