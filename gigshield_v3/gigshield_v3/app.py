"""
GigShield AI — Flask Application (Honest Verification Model)
=============================================================
Verification chain:
  1. Email OTP  — proves worker owns the email address
  2. Self-declared affiliation — worker selects Swiggy/Zomato/Other
                                  clearly labelled NOT API-verified
  3. Document upload — ID card + delivery app screenshot
  4. Admin review   — admin approves or rejects uploaded proof
  5. Subscription   — 7-day weekly plan via UPI QR

Run: python app.py
"""

import os
from functools import wraps
from datetime import datetime

# ── Load .env file FIRST before anything else ─────────────────────
# This makes GMAIL_USER, GMAIL_PASS etc. available via os.environ
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    print("[ENV] .env file loaded ✅")
except ImportError:
    print("[ENV] python-dotenv not installed — reading system env vars only")
    print("[ENV] Install it: pip install python-dotenv")
# ─────────────────────────────────────────────────────────────────

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)

from database import (
    init_db, worker_exists_by_email, create_worker,
    get_worker_by_email, get_worker_by_id, get_all_workers,
    update_otp, verify_otp_db, activate_subscription,
    subscription_active, days_remaining, update_fraud_score,
    update_claim_status, create_claim, get_worker_claims,
    count_claims_this_week, admin_stats, save_doc_paths,
    admin_review_doc, get_pending_docs, is_fraud_ring,
    # Trust score & fraud log (new)
    get_trust_score, apply_trust_penalty, apply_trust_reward,
    is_trust_too_low, log_fraud_event, get_fraud_log,
    get_fraud_rings, get_suspicious_workers, mark_fraud_ring_workers,
)
from ml_model      import ensure_models_trained, predict_income_loss, check_fraud, get_income_chart_data
from weather_service import get_weather, weather_triggers_claim
from qr_generator  import generate_qr
from chatbot       import get_response
from otp_service   import send_otp, generate_otp, verify_otp_expiry
# New modules
from fraud_model   import predict_fraud, fraud_probability, predict_fraud_full
from anti_spoofing import (
    check_rules, check_rules_detail,
    REJECT_STATUSES, SUSPICIOUS_STATUSES, STATUS_REASONS
)

app = Flask(__name__)
app.secret_key   = os.environ.get("SECRET_KEY", "gigshield-dev-2024!")
ADMIN_PASSWORD   = os.environ.get("ADMIN_PASSWORD", "admin123")
UPLOAD_FOLDER    = os.path.join(os.path.dirname(__file__), "static", "uploads")
ALLOWED_EXT      = {"png", "jpg", "jpeg", "gif", "pdf", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

with app.app_context():
    init_db()
    ensure_models_trained()

# ── Helpers ───────────────────────────────────────────────────────

def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def _safe_filename(email, suffix, original):
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else "jpg"
    safe = email.replace("@", "_").replace(".", "_")
    return f"{safe}_{suffix}.{ext}"

def _risk_label(score):
    return "HIGH" if score >= 0.65 else ("MEDIUM" if score >= 0.35 else "LOW")

def _verification_status(worker):
    """Return a dict summarising what steps are complete."""
    w = dict(worker)
    return {
        "email_verified": bool(w.get("email_verified")),
        "docs_uploaded":  bool(w.get("id_card_path") or w.get("app_screenshot_path")),
        "doc_status":     w.get("doc_status", "not_uploaded"),
        "payment_done":   w.get("payment_status") == "paid",
        "fully_verified": (
            bool(w.get("email_verified")) and
            w.get("doc_status") == "approved" and
            w.get("payment_status") == "paid"
        ),
    }

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if "worker_email" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("role_select"))
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("is_admin"):
            flash("Admin access required.", "danger")
            return redirect(url_for("role_select"))
        return f(*a, **k)
    return w

# ── Landing ───────────────────────────────────────────────────────

@app.route("/")
def role_select():
    return render_template("role.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

# ── Registration ──────────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name     = request.form.get("name", "").strip()
    city     = request.form.get("city", "").strip()
    platform = request.form.get("platform", "").strip()
    ref_id   = request.form.get("worker_ref_id", "").strip()
    email    = request.form.get("email", "").strip().lower()
    device_id = request.form.get("device_id", "").strip()

    errors = []
    if not name:                  errors.append("Full name is required.")
    if not city:                  errors.append("City is required.")
    if not platform:              errors.append("Please select your platform.")
    if not email or "@" not in email: errors.append("Valid email address is required.")
    if not errors and worker_exists_by_email(email):
        errors.append("This email is already registered. Please log in.")

    if errors:
        for e in errors: flash(e, "danger")
        return render_template("register.html", form_data=request.form)

    create_worker({
        "name": name, "city": city, "platform": platform,
        "worker_ref_id": ref_id, "email": email, "device_id": device_id,
    })

    otp    = generate_otp()
    update_otp(email, otp)
    result = send_otp(email, otp, worker_id=email, name=name)

    session["reg_email"] = email

    if result["channel"] == "email":
        flash(f"✅ Verification OTP sent to {email}. Check your inbox.", "success")
    else:
        # Never show OTP on screen — only in terminal for dev debugging
        flash(f"📧 OTP sent. Check your terminal if Gmail is not configured.", "info")

    return redirect(url_for("verify_otp_route"))

# ── OTP routes ────────────────────────────────────────────────────

@app.route("/send_otp", methods=["POST"])
def send_otp_route():
    """Resend OTP to session email."""
    email = session.get("reg_email", "")
    if not email:
        return jsonify({"error": "No email in session"}), 400
    w = get_worker_by_email(email)
    if not w:
        return jsonify({"error": "Worker not found"}), 404
    otp    = generate_otp()
    update_otp(email, otp)
    result = send_otp(email, otp, worker_id=email, name=w["name"])
    return jsonify({
        "status":    "sent" if result["success"] else "failed",
        "channel":   result.get("channel", ""),
        "message":   result.get("message", ""),
        "warning":   result.get("warning", ""),
        "debug_otp": "",   # never expose OTP in browser response
    })

@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp_route():
    email = session.get("reg_email", "")
    if not email:
        return redirect(url_for("register"))

    if request.method == "POST":
        entered = request.form.get("otp", "").strip()
        if verify_otp_db(email, entered):
            flash("✅ Email verified! Now upload your documents.", "success")
            return redirect(url_for("upload_docs"))
        flash("❌ Incorrect OTP. Please try again.", "danger")

    return render_template("verify_otp.html", email=email)

# ── Document upload ───────────────────────────────────────────────

@app.route("/upload-docs", methods=["GET", "POST"])
def upload_docs():
    email = session.get("reg_email", "")
    if not email:
        return redirect(url_for("register"))
    w = get_worker_by_email(email)
    if not w:
        return redirect(url_for("register"))
    if not w["email_verified"]:
        flash("Please verify your email first.", "warning")
        return redirect(url_for("verify_otp_route"))

    if request.method == "POST":
        id_path  = ""
        sc_path  = ""

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
        flash("📄 Documents submitted for admin review. You can proceed to payment now.", "success")
        return redirect(url_for("payment"))

    return render_template("upload_docs.html", worker=dict(w))

# ── Payment ───────────────────────────────────────────────────────

@app.route("/payment")
def payment():
    email = session.get("reg_email", "")
    if not email:
        return redirect(url_for("register"))
    w = get_worker_by_email(email)
    if not w:
        return redirect(url_for("register"))
    if not w["email_verified"]:
        flash("Verify your email first.", "warning")
        return redirect(url_for("verify_otp_route"))

    qr = generate_qr(float(w["premium"]), str(w["id"]))
    return render_template("payment.html", worker=dict(w), qr_file=qr)

@app.route("/payment/confirm", methods=["POST"])
def payment_confirm():
    email = session.get("reg_email", "")
    if not email:
        return redirect(url_for("register"))
    activate_subscription(email)
    session["worker_email"] = email
    session.pop("reg_email", None)
    flash("🎉 Subscription activated! Welcome to GigShield AI.", "success")
    return redirect(url_for("worker_dashboard"))

# ── Login ─────────────────────────────────────────────────────────

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
        return redirect(url_for("worker_dashboard"))
    return render_template("worker_login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("role_select"))

# ── Worker Dashboard ──────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def worker_dashboard():
    email = session["worker_email"]
    w = get_worker_by_email(email)
    if not w:
        session.clear()
        return redirect(url_for("role_select"))
    w = dict(w)

    is_active  = subscription_active(email)
    days_left  = days_remaining(email)
    claims     = get_worker_claims(email)
    weather    = get_weather(w["city"])
    pred_loss  = predict_income_loss(3)
    cpw        = count_claims_this_week(email)
    ring       = is_fraud_ring(w.get("device_id", ""), w["id"])
    vstatus    = _verification_status(w)

    fraud = check_fraud({
        "claims_per_week":    cpw,
        "avg_daily_hours":    6.0,
        "gps_variance":       float(w.get("fraud_score", 0) * 500),
        "distance_travelled": 80.0,
        "weather_match":      1,
        "login_frequency":    float(cpw * 2 + 1),
        "has_subscription":   is_active,
        "is_fraud_ring":      ring,
    })
    update_fraud_score(email, fraud["risk_score"], _risk_label(fraud["risk_score"]))

    return render_template("worker_dashboard.html",
        worker=w, is_active=is_active, days_left=days_left,
        claims=claims, weather=weather, predicted_loss=pred_loss,
        risk_score=fraud["risk_score"],
        risk_label=_risk_label(fraud["risk_score"]),
        fraud_data=fraud,
        expiry_warning=(0 < days_left <= 2 and is_active),
        is_fraud_ring=ring, vstatus=vstatus,
    )

# ── Claim ─────────────────────────────────────────────────────────

@app.route("/claim/trigger", methods=["POST"])
@login_required
def trigger_claim():
    """
    Full 5-Step Claim Pipeline:
      1. Subscription check
      2. Doc status check
      3. Weather verification
      4. anti_spoofing.check_rules()    ← rule-based (fast, deterministic)
      5. fraud_model.predict_fraud()    ← ML model
         + trust score gate
      → Final decision + logging
    """
    import logging
    claim_logger = logging.getLogger("gigshield.claims")

    email = session["worker_email"]
    w = get_worker_by_email(email)
    if not w:
        return jsonify({"error": "Worker not found"}), 404
    w = dict(w)
    worker_db_id = w["id"]

    # ── Step 1: Subscription ──────────────────────────────────────
    if not subscription_active(email):
        return jsonify({"status": "rejected",
                        "message": "❌ No active subscription. Please renew."}), 403

    # ── Step 2: Document status ───────────────────────────────────
    if w.get("doc_status") == "pending":
        return jsonify({"status": "rejected",
                        "message": "⏳ Documents under admin review. Claims enabled after approval."}), 403
    if w.get("doc_status") == "rejected":
        return jsonify({"status": "rejected",
                        "message": "❌ Documents rejected. Please re-upload."}), 403

    # ── Step 3: Weather verification ─────────────────────────────
    triggered, weather_info = weather_triggers_claim(w["city"])
    if not triggered:
        return jsonify({"status": "rejected",
                        "message": f"⛅ No disruption in {w['city']}. Current: {weather_info['condition']}"}), 200

    # ── Gather claim inputs ───────────────────────────────────────
    lost_hours = float(request.form.get("lost_hours", 3.0))
    cpw        = count_claims_this_week(email) + 1
    gps_var    = float(request.form.get("gps_variance",    50.0))
    dist_km    = float(request.form.get("distance_km",     80.0))
    avg_hrs    = float(request.form.get("avg_daily_hours",  6.0))
    login_f    = float(request.form.get("login_frequency",  2.0))
    wm         = 1 if weather_info["weather_match"] else 0
    ring       = is_fraud_ring(w.get("device_id", ""), worker_db_id)
    trust_now  = get_trust_score(email)

    # ── Step 4: Rule-based anti-spoofing ─────────────────────────
    rule_input = {
        "weather_match":      wm,
        "claims_per_week":    cpw,
        "gps_variance":       gps_var,
        "distance_travelled": dist_km,
        "login_frequency":    login_f,
        "device_id":          w.get("device_id", ""),
        "worker_db_id":       worker_db_id,
    }
    rule_detail = check_rules_detail(rule_input)
    rule_status = rule_detail["status"]

    # ── Step 5: ML fraud prediction ───────────────────────────────
    ml_result = predict_fraud_full({
        "claims_per_week":    cpw,
        "avg_daily_hours":    avg_hrs,
        "gps_variance":       gps_var,
        "distance_travelled": dist_km,
        "weather_match":      wm,
        "login_frequency":    login_f,
    })
    ml_label = ml_result["ml_label"]   # 0 = genuine, 1 = fraud
    ml_prob  = ml_result["ml_prob"]

    # Also run the fused scorer for risk_score
    fused = check_fraud({
        "claims_per_week":    cpw,
        "avg_daily_hours":    avg_hrs,
        "gps_variance":       gps_var,
        "distance_travelled": dist_km,
        "weather_match":      wm,
        "login_frequency":    login_f,
        "has_subscription":   True,
        "is_fraud_ring":      ring,
    })
    risk_score = fused["risk_score"]

    # Trust score gate (separate from ML — historical behaviour matters)
    trust_blocked = is_trust_too_low(email, threshold=30)

    # ── Final decision ────────────────────────────────────────────
    all_rules_hit = rule_detail["rules_hit"] + fused.get("rules_hit", [])
    all_reasons   = [rule_detail["reason"]] + fused.get("reasons", [])
    # De-duplicate
    all_reasons = list(dict.fromkeys(r for r in all_reasons if r))

    if rule_status in REJECT_STATUSES or ml_label == 1 or trust_blocked:
        # Hard reject
        if trust_blocked:
            event_type = "TRUST_LOW"
            all_reasons.insert(0, f"Trust score too low ({trust_now}/100). Account under review.")
        elif rule_status in REJECT_STATUSES:
            event_type = "RULE_REJECT"
        else:
            event_type = "ML_FRAUD"

        final_status = "rejected"
        payout       = 0
        trust_after  = apply_trust_penalty(email)

    elif rule_status in SUSPICIOUS_STATUSES or fused["decision"] == "REVIEW":
        # Flag for review
        event_type   = "SUSPICIOUS"
        final_status = "review"
        payout       = 0
        trust_after  = trust_now  # no change for review

    else:
        # Approved
        event_type   = "APPROVED"
        final_status = "approved"
        pred_loss    = predict_income_loss(lost_hours)
        payout       = min(pred_loss, float(w["coverage"]))
        trust_after  = apply_trust_reward(email)

    pred_loss = predict_income_loss(lost_hours)

    # ── Persist claim ─────────────────────────────────────────────
    claim_id = create_claim({
        "worker_id":         str(worker_db_id),
        "lost_hours":        lost_hours,
        "predicted_loss":    pred_loss,
        "payout":            payout,
        "weather_event":     weather_info.get("condition", ""),
        "weather_match":     wm,
        "fraud_score":       risk_score,
        "fraud_type":        event_type,
        "rules_hit":         ",".join(all_rules_hit),
        "status":            final_status,
        "rejection_reasons": "; ".join(all_reasons),
    })
    update_claim_status(email, final_status)
    update_fraud_score(email, risk_score, _risk_label(risk_score))

    # Mark fraud ring members
    if ring and w.get("device_id"):
        mark_fraud_ring_workers(w["device_id"])

    # ── Log fraud event ───────────────────────────────────────────
    if final_status in ("rejected", "review"):
        log_fraud_event({
            "worker_id":          str(worker_db_id),
            "email":              email,
            "claim_id":           claim_id,
            "event_type":         event_type,
            "rule_status":        rule_status,
            "ml_label":           ml_label,
            "ml_prob":            ml_prob,
            "risk_score":         risk_score,
            "rules_hit":          ",".join(all_rules_hit),
            "reason":             "; ".join(all_reasons),
            "trust_score_before": trust_now,
            "trust_score_after":  trust_after,
        })
        claim_logger.warning(
            "CLAIM %s | worker=%s | rule=%s | ml=%d (%.2f) | risk=%.3f | trust=%d→%d | %s",
            final_status.upper(), email, rule_status,
            ml_label, ml_prob, risk_score,
            trust_now, trust_after, "; ".join(all_reasons)
        )
    else:
        claim_logger.info(
            "CLAIM APPROVED | worker=%s | payout=₹%.2f | trust=%d→%d",
            email, payout, trust_now, trust_after
        )

    # ── Response ──────────────────────────────────────────────────
    msgs = {
        "approved": f"✅ Claim approved! Payout: ₹{payout:.2f} within 24 hrs. Trust: {trust_after}/100",
        "review":   f"🔍 Flagged for review. Trust score: {trust_after}/100.",
        "rejected": f"❌ Rejected. {all_reasons[0] if all_reasons else 'Fraud detected.'}",
    }
    return jsonify({
        "status":       final_status,
        "message":      msgs[final_status],
        "payout":       payout,
        "rule_status":  rule_status,
        "ml_label":     ml_label,
        "ml_prob":      ml_prob,
        "risk_score":   risk_score,
        "trust_score":  trust_after,
        "weather_event":weather_info.get("condition", ""),
        "reasons":      all_reasons,
        "rules_hit":    all_rules_hit,
    })

# ── Admin ─────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Incorrect password.", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("role_select"))

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    stats       = admin_stats()
    pending     = get_pending_docs()
    hours, losses = get_income_chart_data()
    fraud_logs  = get_fraud_log(limit=20)
    rings       = get_fraud_rings()
    suspicious  = get_suspicious_workers()
    return render_template("admin_dashboard.html",
        stats=stats, pending_docs=pending,
        chart_hours=hours, chart_losses=losses,
        fraud_logs=fraud_logs, fraud_rings=rings,
        suspicious_workers=suspicious)

@app.route("/admin/review/<int:worker_id>", methods=["POST"])
@admin_required
def admin_review(worker_id):
    action = request.form.get("action", "")
    note   = request.form.get("note", "").strip()
    if action in ("approved", "rejected"):
        admin_review_doc(worker_id, action, note, reviewer="admin")
        flash(f"Worker #{worker_id} documents {action}.", "success" if action == "approved" else "warning")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/worker/<int:worker_id>")
@admin_required
def admin_worker_detail(worker_id):
    w = get_worker_by_id(worker_id)
    if not w:
        flash("Worker not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_worker_detail.html", worker=dict(w))

# ── Chatbot & APIs ────────────────────────────────────────────────

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
