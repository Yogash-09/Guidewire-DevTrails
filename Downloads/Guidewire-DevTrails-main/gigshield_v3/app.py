"""
GigShield AI — app.py
=======================
Single Flask app. One server, one port.

  /user/*   → routes_user.py  (worker-facing)
  /admin/*  → routes_admin.py (admin-facing)

Run:  python app.py
"""

import os
from functools import wraps
from datetime import datetime, timedelta
import threading

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from flask import (Flask, render_template, redirect, url_for,
                   request, session, flash, jsonify)

from database import (
    init_db, get_pending_payment_workers,
    worker_exists_by_email, create_worker, get_worker_by_email,
    update_otp, verify_otp_db, activate_subscription,
    subscription_active, days_remaining, save_doc_paths,
)
from ml_model import ensure_models_trained, predict_income_loss
from weather_service import get_weather
from chatbot import get_response
from qr_generator import generate_qr
from otp_service import send_otp, generate_otp, send_email
from routes_user import user_bp
from routes_admin import admin_bp

# ── App ───────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gigshield-dev-2024!")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
ALLOWED_EXT   = {"png", "jpg", "jpeg", "gif", "pdf", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

with app.app_context():
    init_db()
    ensure_models_trained()

# ── Blueprints ────────────────────────────────────────────────────
# /user/*  — worker-facing routes
# /admin/* — admin-facing routes
app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)

# ── Helpers ───────────────────────────────────────────────────────

def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def _safe_filename(email, suffix, original):
    ext  = original.rsplit(".", 1)[-1].lower() if "." in original else "jpg"
    safe = email.replace("@", "_").replace(".", "_")
    return f"{safe}_{suffix}.{ext}"

def _login_required(f):
    @wraps(f)
    def w(*a, **k):
        if "worker_email" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("role_select"))
        return f(*a, **k)
    return w

# ── Payment reminder (throttled, once per hour) ───────────────────

_reminder_lock     = threading.Lock()
_reminder_last_run = None

@app.before_request
def _check_payment_reminders():
    global _reminder_last_run
    with _reminder_lock:
        now = datetime.utcnow()
        if _reminder_last_run and (now - _reminder_last_run).total_seconds() < 3600:
            return
        _reminder_last_run = now
    for w in get_pending_payment_workers():
        try:
            deadline = datetime.fromisoformat(w["payment_deadline"])
        except Exception:
            continue
        now = datetime.utcnow()
        if now >= deadline:
            send_email(w["email"], "Subscription Expired — GigShield AI",
                       "Your payment window has expired. Please re-subscribe.")
        elif now >= deadline - timedelta(hours=6):
            send_email(w["email"], "Payment Reminder — GigShield AI",
                       "Your subscription payment is pending. Please complete it soon.")

# ── Root & shared pages ───────────────────────────────────────────

@app.route("/")
def role_select():
    return render_template("role.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

# ── Worker onboarding flow (/register → /verify_otp → /upload-docs → /payment) ──

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    name      = request.form.get("name", "").strip()
    city      = request.form.get("city", "").strip()
    platform  = request.form.get("platform", "").strip()
    ref_id    = request.form.get("worker_ref_id", "").strip()
    email     = request.form.get("email", "").strip().lower()
    device_id = request.form.get("device_id", "").strip()
    errors = []
    if not name:     errors.append("Full name is required.")
    if not city:     errors.append("City is required.")
    if not platform: errors.append("Please select your platform.")
    if not email or "@" not in email: errors.append("Valid email is required.")
    if not errors and worker_exists_by_email(email):
        errors.append("Email already registered. Please log in.")
    if errors:
        for e in errors: flash(e, "danger")
        return render_template("register.html", form_data=request.form)
    create_worker({"name": name, "city": city, "platform": platform,
                   "worker_ref_id": ref_id, "email": email, "device_id": device_id})
    otp    = generate_otp()
    update_otp(email, otp)
    result = send_otp(email, otp, worker_id=email, name=name)
    session["reg_email"] = email
    session["debug_otp"] = result.get("debug_otp", "")
    flash("OTP sent. Check your inbox or terminal.",
          "success" if result["channel"] == "email" else "info")
    return redirect(url_for("verify_otp_route"))

@app.route("/send_otp", methods=["POST"])
def send_otp_route():
    email = session.get("reg_email", "")
    if not email: return jsonify({"error": "No email in session"}), 400
    w = get_worker_by_email(email)
    if not w: return jsonify({"error": "Worker not found"}), 404
    otp    = generate_otp()
    update_otp(email, otp)
    result = send_otp(email, otp, worker_id=email, name=w["name"])
    session["debug_otp"] = result.get("debug_otp", "")
    return jsonify({"status": "sent" if result["success"] else "failed",
                    "channel": result.get("channel", ""),
                    "debug_otp": result.get("debug_otp", "")})

@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp_route():
    email = session.get("reg_email", "")
    if not email: return redirect(url_for("register"))
    if request.method == "POST":
        if verify_otp_db(email, request.form.get("otp", "").strip()):
            session.pop("debug_otp", None)
            flash("Email verified! Now upload your documents.", "success")
            return redirect(url_for("upload_docs"))
        flash("Incorrect OTP. Try again.", "danger")
    return render_template("verify_otp.html", email=email,
                           debug_otp=session.get("debug_otp", ""))

@app.route("/upload-docs", methods=["GET", "POST"])
def upload_docs():
    email = session.get("reg_email", "")
    if not email: return redirect(url_for("register"))
    w = get_worker_by_email(email)
    if not w or not w["email_verified"]:
        flash("Verify your email first.", "warning")
        return redirect(url_for("verify_otp_route"))
    if request.method == "POST":
        id_path = sc_path = ""
        id_file = request.files.get("id_card")
        sc_file = request.files.get("app_screenshot")
        if id_file and id_file.filename and _allowed_file(id_file.filename):
            fname = _safe_filename(email, "id_card", id_file.filename)
            id_file.save(os.path.join(UPLOAD_FOLDER, fname))
            id_path = f"uploads/{fname}"
        if sc_file and sc_file.filename and _allowed_file(sc_file.filename):
            fname = _safe_filename(email, "screenshot", sc_file.filename)
            sc_file.save(os.path.join(UPLOAD_FOLDER, fname))
            sc_path = f"uploads/{fname}"
        if not id_path and not sc_path:
            flash("Please upload at least one document.", "danger")
            return render_template("upload_docs.html", worker=dict(w))
        save_doc_paths(email, id_path, sc_path)
        flash("📄 Documents submitted for admin review.", "success")
        return redirect(url_for("payment"))
    return render_template("upload_docs.html", worker=dict(w))

@app.route("/payment")
def payment():
    email = session.get("reg_email", "")
    if not email: return redirect(url_for("register"))
    w = get_worker_by_email(email)
    if not w or not w["email_verified"]: return redirect(url_for("verify_otp_route"))
    qr = generate_qr(float(w["premium"]), str(w["id"]))
    return render_template("payment.html", worker=dict(w), qr_file=qr)

@app.route("/payment/confirm", methods=["POST"])
def payment_confirm():
    email = session.get("reg_email", "") or session.get("worker_email", "")
    if not email: return redirect(url_for("register"))
    result = activate_subscription(email)
    if result["result"] == "SUCCESS":
        session["worker_email"] = email
        session.pop("reg_email", None)
        flash("🎉 Payment confirmed! Subscription activated for 7 days.", "success")
        return redirect(url_for("worker_dashboard"))
    flash("❌ Payment window expired. Please re-register.", "danger")
    return redirect(url_for("payment"))

@app.route("/payment/skip")
def payment_skip():
    email = session.get("reg_email", "")
    if email:
        session["worker_email"] = email
        session.pop("reg_email", None)
    flash("⏳ Payment skipped. Complete it before your deadline.", "info")
    return redirect(url_for("worker_dashboard"))

# ── Worker login / logout / dashboard ────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def worker_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        w = get_worker_by_email(email)
        if not w:
            flash("Email not found. Please register first.", "danger")
            return render_template("worker_login.html")
        if not w["email_verified"]:
            session["reg_email"] = email
            flash("Please complete email verification first.", "warning")
            return redirect(url_for("verify_otp_route"))
        session["worker_email"] = email
        session["role"] = "user"
        return redirect(url_for("worker_dashboard"))
    return render_template("worker_login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("role_select"))

@app.route("/dashboard")
@_login_required
def worker_dashboard():
    w = get_worker_by_email(session["worker_email"])
    if not w:
        session.clear()
        return redirect(url_for("role_select"))
    session["user_id"] = w["id"]
    session["role"]    = "user"
    return redirect(url_for("user.home"))

@app.route("/claim/trigger", methods=["POST"])
def trigger_claim():
    if "worker_email" not in session:
        return jsonify({"error": "Not logged in"}), 403
    w = get_worker_by_email(session["worker_email"])
    if not w:
        return jsonify({"error": "Worker not found"}), 404
    session["user_id"] = w["id"]
    session["role"]    = "user"
    from routes_user import trigger_claim as _uc
    return _uc()

# ── Shared APIs ───────────────────────────────────────────────────

@app.route("/chatbot", methods=["POST"])
def chatbot():
    msg = (request.json or {}).get("message", "") or request.form.get("message", "")
    return jsonify({"reply": get_response(msg)})

@app.route("/api/weather/<city>")
def api_weather(city):
    return jsonify(get_weather(city))

@app.route("/api/income-predict")
def api_income():
    h = float(request.args.get("hours", 0))
    return jsonify({"lost_hours": h, "predicted_loss": predict_income_loss(h)})

# ── Error handlers ────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": str(e)}), 500

# ── Entry point ───────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"GigShield AI → http://localhost:{port}")
    print(f"  Worker UI  → http://localhost:{port}/user/login")
    print(f"  Admin UI   → http://localhost:{port}/admin/login")
    app.run(debug=True, host="0.0.0.0", port=port)
