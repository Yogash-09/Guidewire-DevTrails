"""
GigShield AI — anti_spoofing.py
=================================
Pure rule-based anti-spoofing validation layer.

Runs BEFORE the ML model in the claim pipeline.
Returns a simple string status that app.py acts on.

Rule hierarchy (evaluated in order, first match wins):
  REJECT        — hard block, no ML needed
  GPS_SPOOF     — location spoofing detected
  FRAUD_RING    — shared device fingerprint across accounts
  BOT_BEHAVIOR  — automated/scripted login pattern
  SUSPICIOUS    — elevated risk, ML decides
  PASS          — all rules pass, proceed to ML

Usage:
    from anti_spoofing import check_rules, REJECT_STATUSES

    status = check_rules(worker_data)
    if status in REJECT_STATUSES:
        # block claim immediately
"""

import logging
from database import is_fraud_ring

logger = logging.getLogger("gigshield.anti_spoofing")

# ── Thresholds (tunable) ──────────────────────────────────────────
WEATHER_MISMATCH_RULE    = True     # toggle weather check
MAX_CLAIMS_PER_WEEK      = 7        # >7 → SUSPICIOUS
GPS_SPOOF_VARIANCE       = 3000.0   # m² threshold
GPS_STATIC_MIN_DIST      = 2.0      # km — below this + multiple claims = spoof
GPS_STATIC_MIN_CLAIMS    = 3        # min claims to trigger static GPS rule
MAX_LOGIN_FREQUENCY      = 10       # logins/day above this = BOT_BEHAVIOR
FRAUD_RING_MIN_ACCOUNTS  = 1        # shared device with >0 other accounts

# ── Status constants ──────────────────────────────────────────────
STATUS_REJECT      = "REJECT"        # weather mismatch — hard block
STATUS_GPS_SPOOF   = "GPS_SPOOF"     # GPS variance or static
STATUS_FRAUD_RING  = "FRAUD_RING"    # device shared across accounts
STATUS_BOT         = "BOT_BEHAVIOR"  # login frequency anomaly
STATUS_SUSPICIOUS  = "SUSPICIOUS"    # high claim frequency
STATUS_PASS        = "PASS"          # all rules passed

# Statuses that should block a claim without ML scoring
REJECT_STATUSES = {STATUS_REJECT, STATUS_GPS_SPOOF, STATUS_FRAUD_RING}

# Statuses that should flag for review
SUSPICIOUS_STATUSES = {STATUS_BOT, STATUS_SUSPICIOUS}

# Human-readable reason for each status
STATUS_REASONS = {
    STATUS_REJECT:    "Weather conditions do not match official data for your registered city.",
    STATUS_GPS_SPOOF: "GPS location data is inconsistent — possible location spoofing detected.",
    STATUS_FRAUD_RING:"Your device is registered to multiple accounts. Fraud ring suspected.",
    STATUS_BOT:       "Abnormal login frequency detected — automated behaviour suspected.",
    STATUS_SUSPICIOUS:"Unusually high claim frequency this week.",
    STATUS_PASS:      "All anti-spoofing checks passed.",
}


def check_rules(worker: dict) -> str:
    """
    Evaluate all anti-spoofing rules against a worker claim.

    Parameters
    ----------
    worker : dict with keys:
        weather_match       int   1 = verified match, 0 = mismatch
        claims_per_week     int/float
        gps_variance        float  m²
        distance_travelled  float  km
        login_frequency     float  logins/day
        device_id           str
        worker_db_id        int    worker.id (for fraud ring lookup)
        has_subscription    bool

    Returns
    -------
    str  — one of the STATUS_* constants above
    """

    wm       = int(  worker.get("weather_match",       1))
    cpw      = float(worker.get("claims_per_week",     0))
    gpv      = float(worker.get("gps_variance",        0))
    dist     = float(worker.get("distance_travelled",  0))
    login_f  = float(worker.get("login_frequency",     1))
    device   = str(  worker.get("device_id",           ""))
    wid      = int(  worker.get("worker_db_id",        0))

    # ── Rule 1: Weather mismatch (hard reject) ────────────────────
    if WEATHER_MISMATCH_RULE and wm == 0:
        logger.warning("[anti_spoofing] REJECT — weather mismatch worker_id=%s", wid)
        return STATUS_REJECT

    # ── Rule 2: GPS spoofing — high variance ──────────────────────
    if gpv > GPS_SPOOF_VARIANCE:
        logger.warning(
            "[anti_spoofing] GPS_SPOOF — variance=%.0f m² worker_id=%s", gpv, wid
        )
        return STATUS_GPS_SPOOF

    # ── Rule 3: GPS spoofing — static location + multiple claims ──
    if dist < GPS_STATIC_MIN_DIST and cpw > GPS_STATIC_MIN_CLAIMS:
        logger.warning(
            "[anti_spoofing] GPS_SPOOF (static) — dist=%.1f km claims=%d worker_id=%s",
            dist, int(cpw), wid
        )
        return STATUS_GPS_SPOOF

    # ── Rule 4: Fraud ring — shared device fingerprint ────────────
    if device and wid:
        try:
            if is_fraud_ring(device, wid):
                logger.warning(
                    "[anti_spoofing] FRAUD_RING — device=%s shared across accounts worker_id=%s",
                    device[:12], wid
                )
                return STATUS_FRAUD_RING
        except Exception as e:
            logger.error("[anti_spoofing] Fraud ring check failed: %s", e)

    # ── Rule 5: Bot behaviour — abnormal login frequency ──────────
    if login_f > MAX_LOGIN_FREQUENCY:
        logger.warning(
            "[anti_spoofing] BOT_BEHAVIOR — login_freq=%.0f/day worker_id=%s",
            login_f, wid
        )
        return STATUS_BOT

    # ── Rule 6: Too many claims this week ─────────────────────────
    if cpw > MAX_CLAIMS_PER_WEEK:
        logger.warning(
            "[anti_spoofing] SUSPICIOUS — claims/week=%d worker_id=%s", int(cpw), wid
        )
        return STATUS_SUSPICIOUS

    logger.debug("[anti_spoofing] PASS — worker_id=%s", wid)
    return STATUS_PASS


def check_rules_detail(worker: dict) -> dict:
    """
    Extended version that returns full detail dict alongside the status string.
    Useful for admin logging and dashboard display.

    Returns
    -------
    dict:
        status      str    STATUS_* constant
        reason      str    human-readable reason
        is_blocked  bool   True if claim should be blocked
        is_flagged  bool   True if claim should be reviewed
        rules_hit   list   names of all rules that fired
    """
    rules_hit = []
    wm    = int(  worker.get("weather_match",      1))
    cpw   = float(worker.get("claims_per_week",    0))
    gpv   = float(worker.get("gps_variance",       0))
    dist  = float(worker.get("distance_travelled", 0))
    lf    = float(worker.get("login_frequency",    1))
    dev   = str(  worker.get("device_id",          ""))
    wid   = int(  worker.get("worker_db_id",       0))

    # Collect ALL rule violations (not just first)
    if WEATHER_MISMATCH_RULE and wm == 0:
        rules_hit.append("WEATHER_MISMATCH")
    if gpv > GPS_SPOOF_VARIANCE:
        rules_hit.append("GPS_HIGH_VARIANCE")
    if dist < GPS_STATIC_MIN_DIST and cpw > GPS_STATIC_MIN_CLAIMS:
        rules_hit.append("GPS_STATIC")
    if dev and wid:
        try:
            if is_fraud_ring(dev, wid):
                rules_hit.append("FRAUD_RING")
        except Exception:
            pass
    if lf > MAX_LOGIN_FREQUENCY:
        rules_hit.append("HIGH_LOGIN_FREQ")
    if cpw > MAX_CLAIMS_PER_WEEK:
        rules_hit.append("HIGH_CLAIM_FREQ")

    # Primary status = first triggered rule (priority order)
    status = check_rules(worker)

    return {
        "status":     status,
        "reason":     STATUS_REASONS.get(status, "Unknown"),
        "is_blocked": status in REJECT_STATUSES,
        "is_flagged": status in SUSPICIOUS_STATUSES,
        "rules_hit":  rules_hit,
    }
