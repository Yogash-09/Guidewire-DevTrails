"""
GigShield AI — routes_user.py
================================
Blueprint: prefix /user
OTP-based phone login → dashboard → claim
"""

import logging
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, jsonify)

from database import (
    get_worker_by_id, get_worker_by_phone, worker_exists_by_phone,
    update_otp_phone, verify_otp_phone, subscription_active,
    days_remaining, get_worker_claims, count_claims_this_week,
    update_fraud_score, update_claim_status, create_claim,
    is_fraud_ring, get_trust_score, apply_trust_penalty,
    apply_trust_reward, is_trust_too_low, log_fraud_event,
    mark_fraud_ring_workers,
)
from ml_model import predict_income_loss, check_fraud
from weather_service import get_weather, weather_triggers_claim
from otp_service import generate_otp, send_otp_phone
from fraud_model import predict_fraud_full
from anti_spoofing import (
    check_rules_detail, REJECT_STATUSES, SUSPICIOUS_STATUSES, STATUS_REASONS
)
from auth import user_required

user_bp = Blueprint("user", __name__, url_prefix="/user")
claim_logger = logging.getLogger("gigshield.claims")


def _risk_label(score):
    return "HIGH" if score >= 0.65 else ("MEDIUM" if score >= 0.35 else "LOW")


def _vstatus(w: dict) -> dict:
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


# ── Login (phone + OTP) ───────────────────────────────────────────

@user_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("role") == "user":
        return redirect(url_for("user.dashboard"))
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        if not phone:
            flash("Phone number is required.", "danger")
            return render_template("worker_login.html")
        if not worker_exists_by_phone(phone):
            flash("Phone number not registered. Please register first.", "danger")
            return render_template("worker_login.html")
        otp = generate_otp()
        update_otp_phone(phone, otp)
        result = send_otp_phone(phone, otp)
        session["otp_phone"] = phone
        if result.get("success"):
            flash(f"OTP sent to {phone}.", "success")
        else:
            flash("OTP generated. Check terminal (SMS not configured).", "info")
        return redirect(url_for("user.verify_otp"))
    return render_template("worker_login.html")


@user_bp.route("/send_otp", methods=["POST"])
def send_otp_route():
    phone = session.get("otp_phone", "")
    if not phone:
        return jsonify({"error": "No phone in session"}), 400
    otp = generate_otp()
    update_otp_phone(phone, otp)
    result = send_otp_phone(phone, otp)
    return jsonify({
        "status":  "sent" if result.get("success") else "failed",
        "channel": result.get("channel", ""),
        "message": result.get("message", ""),
    })


@user_bp.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    phone = session.get("otp_phone", "")
    if not phone:
        return redirect(url_for("user.login"))
    if request.method == "POST":
        entered = request.form.get("otp", "").strip()
        worker = verify_otp_phone(phone, entered)
        if worker:
            session.pop("otp_phone", None)
            session["user_id"] = worker["id"]
            session["role"] = "user"
            flash("✅ Logged in successfully.", "success")
            return redirect(url_for("user.dashboard"))
        flash("❌ Incorrect OTP. Please try again.", "danger")
    return render_template("verify_otp.html", phone=phone)


@user_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("role_select"))


# ── Dashboard ─────────────────────────────────────────────────────

@user_bp.route("/dashboard")
@user_required
def dashboard():
    w = get_worker_by_id(session["user_id"])
    if not w:
        session.clear()
        return redirect(url_for("role_select"))
    w = dict(w)
    email = w.get("email", "")

    is_active = subscription_active(email)
    days_left = days_remaining(email)
    claims    = get_worker_claims(email)
    weather   = get_weather(w.get("city", ""))
    pred_loss = predict_income_loss(3)
    cpw       = count_claims_this_week(email)
    ring      = is_fraud_ring(w.get("device_id", ""), w["id"])

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
        is_fraud_ring=ring,
        vstatus=_vstatus(w),
    )


# ── Claim ─────────────────────────────────────────────────────────

@user_bp.route("/claim", methods=["POST"])
@user_required
def trigger_claim():
    w = get_worker_by_id(session["user_id"])
    if not w:
        return jsonify({"error": "Worker not found"}), 404
    w = dict(w)
    email        = w.get("email", "")
    worker_db_id = w["id"]

    # Step 1: Subscription
    if not subscription_active(email):
        return jsonify({"status": "rejected",
                        "message": "❌ No active subscription. Please renew."}), 403

    # Step 2: Doc status
    if w.get("doc_status") == "pending":
        return jsonify({"status": "rejected",
                        "message": "⏳ Documents under admin review."}), 403
    if w.get("doc_status") == "rejected":
        return jsonify({"status": "rejected",
                        "message": "❌ Documents rejected. Please re-upload."}), 403

    # Step 3: Weather
    triggered, weather_info = weather_triggers_claim(w.get("city", ""))
    if not triggered:
        return jsonify({"status": "rejected",
                        "message": f"⛅ No disruption in {w.get('city','')}. "
                                   f"Current: {weather_info['condition']}"}), 200

    # Inputs
    lost_hours = float(request.form.get("lost_hours", 3.0))
    cpw        = count_claims_this_week(email) + 1
    gps_var    = float(request.form.get("gps_variance",    50.0))
    dist_km    = float(request.form.get("distance_km",     80.0))
    avg_hrs    = float(request.form.get("avg_daily_hours",  6.0))
    login_f    = float(request.form.get("login_frequency",  2.0))
    wm         = 1 if weather_info["weather_match"] else 0
    ring       = is_fraud_ring(w.get("device_id", ""), worker_db_id)
    trust_now  = get_trust_score(email)

    # Step 4: Rule-based
    rule_detail = check_rules_detail({
        "weather_match":      wm,
        "claims_per_week":    cpw,
        "gps_variance":       gps_var,
        "distance_travelled": dist_km,
        "login_frequency":    login_f,
        "device_id":          w.get("device_id", ""),
        "worker_db_id":       worker_db_id,
    })
    rule_status = rule_detail["status"]

    # Step 5: ML fraud
    ml_result = predict_fraud_full({
        "claims_per_week":    cpw,
        "avg_daily_hours":    avg_hrs,
        "gps_variance":       gps_var,
        "distance_travelled": dist_km,
        "weather_match":      wm,
        "login_frequency":    login_f,
    })
    ml_label = ml_result["ml_label"]
    ml_prob  = ml_result["ml_prob"]

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
    risk_score    = fused["risk_score"]
    trust_blocked = is_trust_too_low(email, threshold=30)

    all_rules_hit = rule_detail["rules_hit"] + fused.get("rules_hit", [])
    all_reasons   = list(dict.fromkeys(
        r for r in ([rule_detail["reason"]] + fused.get("reasons", [])) if r
    ))

    if rule_status in REJECT_STATUSES or ml_label == 1 or trust_blocked:
        event_type   = "TRUST_LOW" if trust_blocked else ("RULE_REJECT" if rule_status in REJECT_STATUSES else "ML_FRAUD")
        final_status = "rejected"
        payout       = 0
        trust_after  = apply_trust_penalty(email)
        if trust_blocked:
            all_reasons.insert(0, f"Trust score too low ({trust_now}/100).")
    elif rule_status in SUSPICIOUS_STATUSES or fused["decision"] == "REVIEW":
        event_type   = "SUSPICIOUS"
        final_status = "review"
        payout       = 0
        trust_after  = trust_now
    else:
        event_type   = "APPROVED"
        final_status = "approved"
        pred_loss    = predict_income_loss(lost_hours)
        payout       = min(pred_loss, float(w.get("coverage", 0)))
        trust_after  = apply_trust_reward(email)

    pred_loss = predict_income_loss(lost_hours)

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

    if ring and w.get("device_id"):
        mark_fraud_ring_workers(w["device_id"])

    if final_status in ("rejected", "review"):
        log_fraud_event({
            "worker_id": str(worker_db_id), "email": email,
            "claim_id": claim_id, "event_type": event_type,
            "rule_status": rule_status, "ml_label": ml_label,
            "ml_prob": ml_prob, "risk_score": risk_score,
            "rules_hit": ",".join(all_rules_hit),
            "reason": "; ".join(all_reasons),
            "trust_score_before": trust_now, "trust_score_after": trust_after,
        })

    msgs = {
        "approved": f"✅ Claim approved! Payout: ₹{payout:.2f}. Trust: {trust_after}/100",
        "review":   f"🔍 Flagged for review. Trust: {trust_after}/100.",
        "rejected": f"❌ Rejected. {all_reasons[0] if all_reasons else 'Fraud detected.'}",
    }
    return jsonify({
        "status": final_status, "message": msgs[final_status],
        "payout": payout, "rule_status": rule_status,
        "ml_label": ml_label, "ml_prob": ml_prob,
        "risk_score": risk_score, "trust_score": trust_after,
        "weather_event": weather_info.get("condition", ""),
        "reasons": all_reasons, "rules_hit": all_rules_hit,
    })
