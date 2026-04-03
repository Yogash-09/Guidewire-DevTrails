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
from weather_service import get_weather
from disruption_service import check_disruption, get_city_risk_level
from triggers import calculate_premium, weather_trigger, pollution_trigger, traffic_trigger
from otp_service import generate_otp, send_otp_phone
from fraud_model import predict_fraud_full
from anti_spoofing import (
    check_rules_detail, REJECT_STATUSES, SUSPICIOUS_STATUSES, STATUS_REASONS
)
from auth import user_required
from qr_generator import generate_qr

user_bp = Blueprint("user", __name__, url_prefix="/user")
claim_logger = logging.getLogger("gigshield.claims")


def _risk_label(score):
    return "HIGH" if score >= 0.65 else ("MEDIUM" if score >= 0.35 else "LOW")


def _vstatus(w: dict) -> dict:
    return {
        "email_verified": bool(w.get("email_verified")),
        "docs_uploaded":  bool(w.get("id_card_path") or w.get("app_screenshot_path")),
        "doc_status":     w.get("doc_status", "not_uploaded"),
        "payment_done":   w.get("payment_status") == "SUCCESS",
        "fully_verified": (
            bool(w.get("email_verified")) and
            w.get("doc_status") == "approved" and
            w.get("payment_status") == "SUCCESS"
        ),
    }


# ── Login (email) ───────────────────────────────────────────────

@user_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("role") == "user":
        return redirect(url_for("user.home"))
    if request.method == "POST":
        from database import worker_exists_by_email, get_worker_by_email
        email = request.form.get("email", "").strip().lower()
        if not email or "@" not in email:
            flash("Valid email address is required.", "danger")
            return render_template("worker_login.html")
        if not worker_exists_by_email(email):
            flash("Email not found. Please register first.", "danger")
            return render_template("worker_login.html")
        w = get_worker_by_email(email)
        if not w["email_verified"]:
            session["reg_email"] = email
            flash("Please complete email verification first.", "warning")
            return redirect(url_for("verify_otp_route"))
        session["user_id"] = w["id"]
        session["role"] = "user"
        flash("✅ Logged in successfully.", "success")
        return redirect(url_for("user.home"))
    return render_template("worker_login.html")


@user_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("role_select"))


# ── Shared worker loader ─────────────────────────────────────────

def _load_worker():
    """Load worker dict from session, return None if not found."""
    w = get_worker_by_id(session.get("user_id"))
    return dict(w) if w else None


def _base_ctx(w: dict) -> dict:
    """Common template context shared across all user pages."""
    email = w.get("email", "")
    return dict(
        worker=w,
        worker_name=w.get("name", ""),
        is_active=subscription_active(email),
        days_left=days_remaining(email),
        vstatus=_vstatus(w),
    )


# ── Dashboard (legacy redirect) ───────────────────────────────────

@user_bp.route("/dashboard")
@user_required
def dashboard():
    return redirect(url_for("user.home"))


# ── Home ──────────────────────────────────────────────────────────

@user_bp.route("/home")
@user_required
def home():
    w = _load_worker()
    if not w:
        session.clear()
        return redirect(url_for("role_select"))
    ctx = _base_ctx(w)
    city = w.get("city", "")
    ctx["weather"]        = get_weather(city)
    ctx["predicted_loss"] = predict_income_loss(3)
    ctx["active_page"]    = "home"
    # Pass disruption summary for zero-touch UX banner
    disrupted, dis_info   = check_disruption(city)
    ctx["disruption"]     = dis_info
    ctx["disrupted"]      = disrupted
    return render_template("user_home.html", **ctx)


# ── Verification ──────────────────────────────────────────────────

@user_bp.route("/verification")
@user_required
def verification():
    w = _load_worker()
    if not w:
        session.clear()
        return redirect(url_for("role_select"))
    ctx = _base_ctx(w)
    ctx["active_page"] = "verification"
    return render_template("user_verification.html", **ctx)


# ── Claims page ───────────────────────────────────────────────────

@user_bp.route("/claims")
@user_required
def claims():
    w = _load_worker()
    if not w:
        session.clear()
        return redirect(url_for("role_select"))
    ctx = _base_ctx(w)
    ctx["claims"]      = get_worker_claims(w.get("email", ""))
    ctx["active_page"] = "claims"
    return render_template("user_claims.html", **ctx)


# ── Subscription page ─────────────────────────────────────────────

@user_bp.route("/subscription")
@user_required
def subscription():
    w = _load_worker()
    if not w:
        session.clear()
        return redirect(url_for("role_select"))
    ctx = _base_ctx(w)
    ctx["qr_file"]     = generate_qr(float(w.get("premium", 49)), str(w["id"]))
    ctx["active_page"] = "subscription"
    return render_template("user_subscription.html", **ctx)


# ── AI Assistant page ─────────────────────────────────────────────

@user_bp.route("/assistant")
@user_required
def assistant():
    w = _load_worker()
    if not w:
        session.clear()
        return redirect(url_for("role_select"))
    ctx = _base_ctx(w)
    ctx["active_page"] = "assistant"
    return render_template("user_assistant.html", **ctx)


# ── Skip payment ──────────────────────────────────────────────────

@user_bp.route("/skip-payment")
@user_required
def skip_payment():
    flash("⏳ Payment skipped. Complete it before your deadline to activate coverage.", "info")
    return redirect(url_for("user.home"))


# ── Payment confirm (from subscription page) ─────────────────────────

@user_bp.route("/payment/confirm", methods=["POST"])
@user_required
def payment_confirm():
    from database import activate_subscription
    w = _load_worker()
    if not w:
        session.clear()
        return redirect(url_for("role_select"))
    result = activate_subscription(w["email"])
    if result["result"] == "SUCCESS":
        flash("🎉 Payment confirmed! Subscription activated for 7 days.", "success")
    else:
        flash("❌ Payment window expired. Please re-register to get a new payment window.", "danger")
    return redirect(url_for("user.subscription"))


# ── Disruption check API (polling) ──────────────────────────────

@user_bp.route("/disruption-check")
@user_required
def disruption_check():
    """JSON endpoint — frontend polls this to show live disruption status."""
    w = _load_worker()
    if not w:
        return jsonify({"error": "Not found"}), 404
    triggered, info = check_disruption(w.get("city", ""))
    return jsonify({
        "triggered":      triggered,
        "triggers_fired": info["triggers_fired"],
        "trigger_count":  info["trigger_count"],
        "primary_reason": info["primary_reason"],
        "aqi":            info["aqi"]["aqi"],
        "congestion":     info["traffic"]["congestion_index"],
        "weather":        info["weather"].get("condition", ""),
        "is_active":      subscription_active(w.get("email", "")),
    })


# ── Zero-touch auto-claim ─────────────────────────────────────────

@user_bp.route("/auto-claim", methods=["POST"])
@user_required
def auto_claim():
    """
    Zero-touch claim: system calls this automatically when disruption is detected.
    No manual input required — lost_hours defaults to 3h.
    """
    w = get_worker_by_id(session["user_id"])
    if not w:
        return jsonify({"error": "Worker not found"}), 404
    w = dict(w)
    email        = w.get("email", "")
    worker_db_id = w["id"]

    if not subscription_active(email):
        return jsonify({"status": "skipped", "message": "Subscription not active."}), 200

    triggered, dis_info = check_disruption(w.get("city", ""))
    if not triggered:
        return jsonify({"status": "skipped",
                        "message": f"No disruption detected in {w.get('city','')}"}), 200

    # Use default 3h lost for auto-claim
    return _process_claim(w, email, worker_db_id, dis_info, lost_hours=3.0, auto=True)


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

    if not subscription_active(email):
        pay_status = w.get("payment_status", "PENDING")
        if pay_status == "PENDING":
            msg = "⏳ Subscription inactive — payment pending. Complete payment before deadline."
        elif pay_status == "EXPIRED":
            msg = "❌ Payment window expired. Please re-subscribe to continue coverage."
        else:
            msg = "❌ No active subscription. Please renew."
        return jsonify({"status": "rejected", "message": msg}), 403

    if w.get("doc_status") == "pending":
        return jsonify({"status": "rejected", "message": "⏳ Documents under admin review."}), 403
    if w.get("doc_status") == "rejected":
        return jsonify({"status": "rejected", "message": "❌ Documents rejected. Please re-upload."}), 403

    triggered, dis_info = check_disruption(w.get("city", ""))
    if not triggered:
        return jsonify({"status": "rejected",
                        "message": f"⛅ No disruption in {w.get('city','')}. "
                                   f"{dis_info['primary_reason']}"}), 200

    lost_hours = float(request.form.get("lost_hours", 3.0))
    return _process_claim(w, email, worker_db_id, dis_info, lost_hours=lost_hours, auto=False)


def _process_claim(w: dict, email: str, worker_db_id: int,
                   dis_info: dict, lost_hours: float, auto: bool) -> object:
    """Shared claim processing logic for both manual and auto-claim paths."""
    cpw     = count_claims_this_week(email) + 1
    gps_var = float(w.get("fraud_score", 0) * 500)   # proxy from stored fraud score
    dist_km = 80.0
    avg_hrs = 6.0
    login_f = float(cpw * 2 + 1)
    wm      = 1 if dis_info["weather"].get("is_disrupted") else 0
    ring    = is_fraud_ring(w.get("device_id", ""), worker_db_id)
    trust_now = get_trust_score(email)

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

    ml_result  = predict_fraud_full({
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

    # Build trigger label from all fired sources
    trigger_type    = ",".join(dis_info.get("triggers_fired", ["WEATHER"])) or "WEATHER"
    trigger_sources = dis_info.get("primary_reason", "")
    aqi_val         = dis_info.get("aqi", {}).get("aqi", 0)
    cong_idx        = dis_info.get("traffic", {}).get("congestion_index", 0.0)

    claim_id = create_claim({
        "worker_id":         str(worker_db_id),
        "lost_hours":        lost_hours,
        "predicted_loss":    pred_loss,
        "payout":            payout,
        "trigger_type":      trigger_type,
        "trigger_sources":   trigger_sources,
        "aqi_value":         aqi_val,
        "congestion_index":  cong_idx,
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

    prefix = "🤖 Auto-claim" if auto else "Manual claim"
    msgs = {
        "approved": f"✅ {prefix} approved! Payout: ₹{payout:.2f}. Triggers: {trigger_type}",
        "review":   f"🔍 {prefix} flagged for review. Trust: {trust_after}/100.",
        "rejected": f"❌ {prefix} rejected. {all_reasons[0] if all_reasons else 'Fraud detected.'}",
    }
    return jsonify({
        "status": final_status, "message": msgs[final_status],
        "payout": payout, "rule_status": rule_status,
        "ml_label": ml_label, "ml_prob": ml_prob,
        "risk_score": risk_score, "trust_score": trust_after,
        "trigger_type": trigger_type,
        "triggers_fired": dis_info.get("triggers_fired", []),
        "primary_reason": dis_info.get("primary_reason", ""),
        "reasons": all_reasons, "rules_hit": all_rules_hit,
    })
