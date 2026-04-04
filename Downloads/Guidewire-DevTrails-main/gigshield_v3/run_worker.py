"""
GigShield AI — Worker Portal (port 5000)
==========================================
Only exposes worker-facing routes.
Run: python run_worker.py
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from functools import wraps

from database import (
    init_db, worker_exists_by_email, create_worker, get_worker_by_email,
    update_otp, verify_otp_db, activate_subscription, subscription_active,
    days_remaining, save_doc_paths,
)
from ml_model import ensure_models_trained, predict_income_loss
from weather_service import get_weather
from chatbot import get_response
from qr_generator import generate_qr
from otp_service import generate_otp, send_otp
from routes_user import user_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gigshield-worker-2024!")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
ALLOWED_EXT   = {"png", "jpg", "jpeg", "gif", "pdf", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

with app.app_context():
    init_db()
    ensure_models_trained()

# ── Worker blueprint (/user/*) ────────────────────────────────────
app.register_blueprint(user_bp)

# ── Helpers ───────────────────────────────────────────────────────
def _allowed_file(f): return "." in f and f.rsplit(".",1)[1].lower() in ALLOWED_EXT
def _safe_filename(email, suffix, original):
    ext  = original.rsplit(".",1)[-1].lower() if "." in original else "jpg"
    safe = email.replace("@","_").replace(".","_")
    return f"{safe}_{suffix}.{ext}"

def _login_required(f):
    @wraps(f)
    def w(*a,**k):
        if "worker_email" not in session:
            flash("Please log in first.","warning")
            return redirect(url_for("role_select"))
        return f(*a,**k)
    return w

# ── Pages ─────────────────────────────────────────────────────────

@app.route("/")
def role_select():
    return render_template("role_worker.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    name      = request.form.get("name","").strip()
    city      = request.form.get("city","").strip()
    platform  = request.form.get("platform","").strip()
    ref_id    = request.form.get("worker_ref_id","").strip()
    email     = request.form.get("email","").strip().lower()
    device_id = request.form.get("device_id","").strip()
    errors = []
    if not name:    errors.append("Full name is required.")
    if not city:    errors.append("City is required.")
    if not platform: errors.append("Please select your platform.")
    if not email or "@" not in email: errors.append("Valid email is required.")
    if not errors and worker_exists_by_email(email):
        errors.append("Email already registered. Please log in.")
    if errors:
        for e in errors: flash(e,"danger")
        return render_template("register.html", form_data=request.form)
    create_worker({"name":name,"city":city,"platform":platform,
                   "worker_ref_id":ref_id,"email":email,"device_id":device_id})
    otp    = generate_otp()
    update_otp(email, otp)
    result = send_otp(email, otp, worker_id=email, name=name)
    session["reg_email"] = email
    flash("OTP sent. Check your inbox or terminal.", "success" if result["channel"]=="email" else "info")
    return redirect(url_for("verify_otp_route"))

@app.route("/send_otp", methods=["POST"])
def send_otp_route():
    email = session.get("reg_email","")
    if not email: return jsonify({"error":"No email in session"}),400
    w = get_worker_by_email(email)
    if not w: return jsonify({"error":"Worker not found"}),404
    otp = generate_otp(); update_otp(email, otp)
    result = send_otp(email, otp, worker_id=email, name=w["name"])
    return jsonify({"status":"sent" if result["success"] else "failed","channel":result.get("channel","")})

@app.route("/verify_otp", methods=["GET","POST"])
def verify_otp_route():
    email = session.get("reg_email","")
    if not email: return redirect(url_for("register"))
    if request.method == "POST":
        if verify_otp_db(email, request.form.get("otp","").strip()):
            flash("Email verified! Now upload your documents.","success")
            return redirect(url_for("upload_docs"))
        flash("Incorrect OTP.","danger")
    return render_template("verify_otp.html", email=email)

@app.route("/upload-docs", methods=["GET","POST"])
def upload_docs():
    email = session.get("reg_email","")
    if not email: return redirect(url_for("register"))
    w = get_worker_by_email(email)
    if not w or not w["email_verified"]:
        flash("Verify your email first.","warning")
        return redirect(url_for("verify_otp_route"))
    if request.method == "POST":
        id_path = sc_path = ""
        id_file = request.files.get("id_card")
        sc_file = request.files.get("app_screenshot")
        if id_file and id_file.filename and _allowed_file(id_file.filename):
            fname = _safe_filename(email,"id_card",id_file.filename)
            id_file.save(os.path.join(UPLOAD_FOLDER,fname)); id_path=f"uploads/{fname}"
        if sc_file and sc_file.filename and _allowed_file(sc_file.filename):
            fname = _safe_filename(email,"screenshot",sc_file.filename)
            sc_file.save(os.path.join(UPLOAD_FOLDER,fname)); sc_path=f"uploads/{fname}"
        if not id_path and not sc_path:
            flash("Please upload at least one document.","danger")
            return render_template("upload_docs.html", worker=dict(w))
        save_doc_paths(email, id_path, sc_path)
        flash("Documents submitted for admin review.","success")
        return redirect(url_for("payment"))
    return render_template("upload_docs.html", worker=dict(w))

@app.route("/payment")
def payment():
    email = session.get("reg_email","")
    if not email: return redirect(url_for("register"))
    w = get_worker_by_email(email)
    if not w or not w["email_verified"]: return redirect(url_for("verify_otp_route"))
    qr = generate_qr(float(w["premium"]), str(w["id"]))
    return render_template("payment.html", worker=dict(w), qr_file=qr)

@app.route("/payment/confirm", methods=["POST"])
def payment_confirm():
    email = session.get("reg_email","")
    if not email: return redirect(url_for("register"))
    activate_subscription(email)
    session["worker_email"] = email
    session.pop("reg_email", None)
    flash("Subscription activated! Welcome to GigShield AI.","success")
    return redirect(url_for("worker_dashboard"))

@app.route("/login", methods=["GET","POST"])
def worker_login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        w = get_worker_by_email(email)
        if not w:
            flash("Email not found. Please register first.","danger")
            return render_template("worker_login.html")
        if not w["email_verified"]:
            session["reg_email"] = email
            flash("Please complete email verification first.","warning")
            return redirect(url_for("verify_otp_route"))
        session["worker_email"] = email
        return redirect(url_for("worker_dashboard"))
    return render_template("worker_login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("role_select"))

@app.route("/dashboard")
@_login_required
def worker_dashboard():
    from database import (get_worker_claims, count_claims_this_week,
                          update_fraud_score, is_fraud_ring)
    from ml_model import check_fraud

    def _rl(s): return "HIGH" if s>=0.65 else ("MEDIUM" if s>=0.35 else "LOW")
    def _vs(w): return {
        "email_verified": bool(w.get("email_verified")),
        "docs_uploaded":  bool(w.get("id_card_path") or w.get("app_screenshot_path")),
        "doc_status":     w.get("doc_status","not_uploaded"),
        "payment_done":   w.get("payment_status")=="paid",
        "fully_verified": bool(w.get("email_verified")) and w.get("doc_status")=="approved" and w.get("payment_status")=="paid",
    }
    email = session["worker_email"]
    w = get_worker_by_email(email)
    if not w: session.clear(); return redirect(url_for("role_select"))
    w = dict(w)
    is_active = subscription_active(email)
    days_left = days_remaining(email)
    claims    = get_worker_claims(email)
    weather   = get_weather(w["city"])
    pred_loss = predict_income_loss(3)
    cpw       = count_claims_this_week(email)
    ring      = is_fraud_ring(w.get("device_id",""), w["id"])
    fraud = check_fraud({"claims_per_week":cpw,"avg_daily_hours":6.0,
        "gps_variance":float(w.get("fraud_score",0)*500),"distance_travelled":80.0,
        "weather_match":1,"login_frequency":float(cpw*2+1),
        "has_subscription":is_active,"is_fraud_ring":ring})
    update_fraud_score(email, fraud["risk_score"], _rl(fraud["risk_score"]))
    return render_template("worker_dashboard.html",
        worker=w, is_active=is_active, days_left=days_left,
        claims=claims, weather=weather, predicted_loss=pred_loss,
        risk_score=fraud["risk_score"], risk_label=_rl(fraud["risk_score"]),
        fraud_data=fraud, expiry_warning=(0<days_left<=2 and is_active),
        is_fraud_ring=ring, vstatus=_vs(w))

@app.route("/claim/trigger", methods=["POST"])
@_login_required
def trigger_claim():
    from database import get_worker_by_email as _gwe
    w = _gwe(session["worker_email"])
    if not w: return jsonify({"error":"Worker not found"}),404
    session["user_id"] = w["id"]
    session["role"]    = "user"
    from routes_user import trigger_claim as _uc
    return _uc()

# ── APIs ──────────────────────────────────────────────────────────

@app.route("/chatbot", methods=["POST"])
def chatbot():
    msg = (request.json or {}).get("message","") or request.form.get("message","")
    return jsonify({"reply": get_response(msg)})

@app.route("/api/weather/<city>")
def api_weather(city): return jsonify(get_weather(city))

@app.route("/api/income-predict")
def api_income():
    h = float(request.args.get("hours",0))
    return jsonify({"lost_hours":h,"predicted_loss":predict_income_loss(h)})

@app.errorhandler(404)
def not_found(_): return render_template("404.html"),404

@app.errorhandler(500)
def server_error(e): return jsonify({"error":str(e)}),500

if __name__ == "__main__":
    print("Worker Portal → http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
