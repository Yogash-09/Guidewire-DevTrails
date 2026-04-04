"""
GigShield AI — Database (SQLite)
==================================
Honest verification model:
  - Email OTP (no phone OTP)
  - Platform is SELF-DECLARED (not API-verified)
  - Document upload → admin approves/rejects
  - Admin sets final verified status
"""

import sqlite3, os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gigshield.db")

def get_conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS workers (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT    NOT NULL,
            city                 TEXT    NOT NULL,

            -- Self-declared affiliation (NOT verified by Swiggy/Zomato API)
            platform             TEXT    NOT NULL,
            worker_ref_id        TEXT    DEFAULT '',   -- self-entered reference ID

            -- Contact
            email                TEXT    UNIQUE NOT NULL,

            -- Email OTP
            otp_code             TEXT    DEFAULT '',
            email_verified       INTEGER DEFAULT 0,

            -- Document proof (uploaded by worker, reviewed by admin)
            id_card_path         TEXT    DEFAULT '',
            app_screenshot_path  TEXT    DEFAULT '',

            -- Admin verification decision
            doc_status           TEXT    DEFAULT 'not_uploaded',
            -- not_uploaded | pending | approved | rejected
            doc_review_note      TEXT    DEFAULT '',
            doc_reviewed_by      TEXT    DEFAULT '',
            doc_reviewed_at      TEXT    DEFAULT '',

            -- Subscription
            payment_status       TEXT    DEFAULT 'PENDING',
            subscription_status  TEXT    DEFAULT 'INACTIVE',
            subscription_start   TEXT    DEFAULT '',
            subscription_end     TEXT    DEFAULT '',
            payment_deadline     TEXT    DEFAULT '',
            premium              REAL    DEFAULT 0,
            coverage             REAL    DEFAULT 0,
            city_risk_level      TEXT    DEFAULT 'LOW',

            -- Runtime
            claim_status         TEXT    DEFAULT 'none',
            fraud_score          REAL    DEFAULT 0,
            risk_label           TEXT    DEFAULT 'LOW',
            device_id            TEXT    DEFAULT '',
            created_at           TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS claims (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id         TEXT    NOT NULL,
            claim_date        TEXT    DEFAULT (datetime('now')),
            lost_hours        REAL    DEFAULT 0,
            predicted_loss    REAL    DEFAULT 0,
            payout            REAL    DEFAULT 0,
            trigger_type      TEXT    DEFAULT '',
            trigger_sources   TEXT    DEFAULT '',
            aqi_value         INTEGER DEFAULT 0,
            congestion_index  REAL    DEFAULT 0,
            fraud_score       REAL    DEFAULT 0,
            fraud_type        TEXT    DEFAULT '',
            rules_hit         TEXT    DEFAULT '',
            status            TEXT    DEFAULT 'pending',
            rejection_reasons TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS otp_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    NOT NULL,
            otp         TEXT    NOT NULL,
            worker_id   TEXT    DEFAULT '',
            created_at  TEXT    DEFAULT (datetime('now')),
            expires_at  TEXT    NOT NULL,
            used        INTEGER DEFAULT 0,
            delivered   INTEGER DEFAULT 0,
            channel     TEXT    DEFAULT 'console'
        );

        CREATE TABLE IF NOT EXISTS device_registry (
            device_id     TEXT NOT NULL,
            worker_id     TEXT NOT NULL,
            registered_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (device_id, worker_id)
        );

        CREATE TABLE IF NOT EXISTS fraud_log (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id          TEXT    NOT NULL,
            email              TEXT    DEFAULT '',
            claim_id           INTEGER DEFAULT 0,
            event_type         TEXT    NOT NULL,
            rule_status        TEXT    DEFAULT '',
            ml_label           INTEGER DEFAULT 0,
            ml_prob            REAL    DEFAULT 0,
            risk_score         REAL    DEFAULT 0,
            rules_hit          TEXT    DEFAULT '',
            reason             TEXT    DEFAULT '',
            trust_score_before INTEGER DEFAULT 100,
            trust_score_after  INTEGER DEFAULT 100,
            logged_at          TEXT    DEFAULT (datetime('now'))
        );
        """)

    # Non-destructive migrations
    with get_conn() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(workers)").fetchall()]
        if "trust_score" not in cols:
            c.execute("ALTER TABLE workers ADD COLUMN trust_score INTEGER DEFAULT 100")
            print("[DB] Migration: trust_score column added")
        if "phone_number" not in cols:
            c.execute("ALTER TABLE workers ADD COLUMN phone_number TEXT DEFAULT ''")
            print("[DB] Migration: phone_number column added")
        if "otp_verified" not in cols:
            c.execute("ALTER TABLE workers ADD COLUMN otp_verified INTEGER DEFAULT 0")
            print("[DB] Migration: otp_verified column added")
        if "payment_deadline" not in cols:
            c.execute("ALTER TABLE workers ADD COLUMN payment_deadline TEXT DEFAULT ''")
            print("[DB] Migration: payment_deadline column added")
        if "subscription_status" not in cols:
            c.execute("ALTER TABLE workers ADD COLUMN subscription_status TEXT DEFAULT 'INACTIVE'")
            print("[DB] Migration: subscription_status column added")
        if "city_risk_level" not in cols:
            c.execute("ALTER TABLE workers ADD COLUMN city_risk_level TEXT DEFAULT 'LOW'")
            print("[DB] Migration: city_risk_level column added")

    # Claims table migration
    with get_conn() as c:
        claim_cols = [r[1] for r in c.execute("PRAGMA table_info(claims)").fetchall()]
        if "trigger_type" not in claim_cols:
            c.execute("ALTER TABLE claims ADD COLUMN trigger_type TEXT DEFAULT ''")
            print("[DB] Migration: claims.trigger_type added")
        if "trigger_sources" not in claim_cols:
            c.execute("ALTER TABLE claims ADD COLUMN trigger_sources TEXT DEFAULT ''")
            print("[DB] Migration: claims.trigger_sources added")
        if "aqi_value" not in claim_cols:
            c.execute("ALTER TABLE claims ADD COLUMN aqi_value INTEGER DEFAULT 0")
            print("[DB] Migration: claims.aqi_value added")
        if "congestion_index" not in claim_cols:
            c.execute("ALTER TABLE claims ADD COLUMN congestion_index REAL DEFAULT 0")
            print("[DB] Migration: claims.congestion_index added")

    print(f"[DB] Ready -> {DB_PATH}")

# ── Workers ───────────────────────────────────────────────────────

def worker_exists_by_email(email: str) -> bool:
    with get_conn() as c:
        return c.execute("SELECT id FROM workers WHERE email=?", (email,)).fetchone() is not None

def worker_exists_by_phone(phone: str) -> bool:
    with get_conn() as c:
        return c.execute("SELECT id FROM workers WHERE phone_number=?", (phone.strip(),)).fetchone() is not None

def get_worker_by_phone(phone: str):
    with get_conn() as c:
        return c.execute("SELECT * FROM workers WHERE phone_number=?", (phone.strip(),)).fetchone()

def update_otp_phone(phone: str, otp: str):
    """Store OTP against a phone number."""
    with get_conn() as c:
        c.execute("UPDATE workers SET otp_code=?, otp_verified=0 WHERE phone_number=?",
                  (otp, phone.strip()))

def verify_otp_phone(phone: str, entered: str):
    """Verify OTP for phone login. Returns worker row on success, None on failure."""
    with get_conn() as c:
        row = c.execute(
            "SELECT * FROM workers WHERE phone_number=?", (phone.strip(),)
        ).fetchone()
    if row and str(row["otp_code"]).strip() == str(entered).strip():
        with get_conn() as c:
            c.execute("UPDATE workers SET otp_verified=1 WHERE phone_number=?",
                      (phone.strip(),))
        return row
    return None

def create_worker(data: dict) -> int:
    from triggers import calculate_premium, get_city_risk_level
    city         = data.get("city", "")
    cpw          = data.get("claim_history", 0)   # past claims used as proxy
    risk_level   = get_city_risk_level(city)
    premium      = calculate_premium(city, claims_per_week=cpw, weather_risk=risk_level)
    coverage     = round(premium * 20, 2)
    now          = datetime.utcnow()
    deadline     = now + timedelta(hours=24)
    with get_conn() as c:
        cur = c.execute(
            """INSERT INTO workers
               (name,city,platform,worker_ref_id,email,device_id,premium,coverage,
                payment_status,subscription_status,subscription_start,payment_deadline,
                city_risk_level)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["city"], data["platform"],
             data.get("worker_ref_id",""),
             data["email"].lower().strip(),
             data.get("device_id",""),
             premium, coverage,
             "PENDING", "INACTIVE",
             now.isoformat(), deadline.isoformat(),
             risk_level)
        )
        if data.get("device_id"):
            c.execute(
                "INSERT OR IGNORE INTO device_registry (device_id,worker_id) VALUES (?,?)",
                (data["device_id"], str(cur.lastrowid))
            )
        return cur.lastrowid


def update_premium(email: str, premium: float, coverage: float, risk_level: str):
    """Recalculate and persist dynamic premium for an existing worker."""
    with get_conn() as c:
        c.execute(
            "UPDATE workers SET premium=?, coverage=?, city_risk_level=? WHERE email=?",
            (premium, coverage, risk_level, email.lower().strip())
        )

def get_worker_by_email(email: str):
    with get_conn() as c:
        return c.execute("SELECT * FROM workers WHERE email=?",
                         (email.lower().strip(),)).fetchone()

def get_worker_by_id(worker_db_id: int):
    with get_conn() as c:
        return c.execute("SELECT * FROM workers WHERE id=?", (worker_db_id,)).fetchone()

def get_all_workers():
    with get_conn() as c:
        return c.execute("SELECT * FROM workers ORDER BY created_at DESC").fetchall()

def update_otp(email: str, otp: str):
    with get_conn() as c:
        c.execute("UPDATE workers SET otp_code=? WHERE email=?",
                  (otp, email.lower().strip()))

def verify_otp_db(email: str, entered: str) -> bool:
    with get_conn() as c:
        row = c.execute("SELECT otp_code FROM workers WHERE email=?",
                        (email.lower().strip(),)).fetchone()
    if row and str(row["otp_code"]).strip() == str(entered).strip():
        with get_conn() as c:
            c.execute("UPDATE workers SET email_verified=1 WHERE email=?",
                      (email.lower().strip(),))
        return True
    return False

# ── Document upload & admin review ───────────────────────────────

def save_doc_paths(email: str, id_card_path: str = "", screenshot_path: str = ""):
    with get_conn() as c:
        c.execute(
            "UPDATE workers SET id_card_path=?, app_screenshot_path=?, doc_status='pending' WHERE email=?",
            (id_card_path, screenshot_path, email.lower().strip())
        )

def admin_review_doc(worker_db_id: int, status: str, note: str = "", reviewer: str = "admin"):
    """status = 'approved' or 'rejected'"""
    with get_conn() as c:
        c.execute(
            """UPDATE workers
               SET doc_status=?, doc_review_note=?, doc_reviewed_by=?, doc_reviewed_at=?
               WHERE id=?""",
            (status, note, reviewer, datetime.utcnow().isoformat(), worker_db_id)
        )

def get_pending_docs():
    with get_conn() as c:
        return c.execute(
            """SELECT * FROM workers
               WHERE doc_status='pending'
               AND (id_card_path!='' OR app_screenshot_path!='')
               ORDER BY created_at DESC"""
        ).fetchall()

# ── Subscription ──────────────────────────────────────────────────

def activate_subscription(email: str) -> dict:
    """Activate if within deadline, else mark EXPIRED. Returns result dict."""
    email = email.lower().strip()
    with get_conn() as c:
        r = c.execute(
            "SELECT payment_deadline, name FROM workers WHERE email=?", (email,)
        ).fetchone()
    now = datetime.utcnow()
    try:
        deadline = datetime.fromisoformat(r["payment_deadline"]) if r and r["payment_deadline"] else now
    except Exception:
        deadline = now

    if now <= deadline:
        end = now + timedelta(days=7)
        with get_conn() as c:
            c.execute(
                """UPDATE workers
                   SET payment_status='SUCCESS', subscription_status='ACTIVE',
                       subscription_end=?
                   WHERE email=?""",
                (end.isoformat(), email)
            )
        # Send activation confirmation email
        try:
            from otp_service import send_email
            name = r["name"] if r else "Worker"
            send_email(
                email,
                "Subscription Activated — GigShield AI",
                f"Hello {name},\n\nYour GigShield AI subscription is now ACTIVE.\n"
                f"Coverage period: {now.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}\n"
                f"You are now protected against weather and disruption-based income loss.\n\n"
                f"— GigShield AI Team"
            )
        except Exception:
            pass
        return {"result": "SUCCESS", "subscription_end": end.isoformat()}
    else:
        with get_conn() as c:
            c.execute(
                "UPDATE workers SET payment_status='EXPIRED', subscription_status='INACTIVE' WHERE email=?",
                (email,)
            )
        return {"result": "EXPIRED"}

def subscription_active(email: str) -> bool:
    with get_conn() as c:
        r = c.execute(
            "SELECT subscription_end, payment_status FROM workers WHERE email=?",
            (email.lower().strip(),)
        ).fetchone()
    if not r or r["payment_status"] != "SUCCESS": return False
    try:
        return datetime.utcnow() <= datetime.fromisoformat(r["subscription_end"])
    except Exception:
        return False

def get_pending_payment_workers() -> list:
    """Return workers with PENDING payment for reminder checks."""
    with get_conn() as c:
        rows = c.execute(
            "SELECT email, name, payment_deadline FROM workers WHERE payment_status='PENDING'"
        ).fetchall()
    return [dict(r) for r in rows]

def days_remaining(email: str) -> int:
    with get_conn() as c:
        r = c.execute("SELECT subscription_end FROM workers WHERE email=?",
                      (email.lower().strip(),)).fetchone()
    if not r or not r["subscription_end"]: return 0
    try:
        return max(0, (datetime.fromisoformat(r["subscription_end"]) - datetime.utcnow()).days)
    except Exception:
        return 0

def update_fraud_score(email: str, score: float, label: str):
    with get_conn() as c:
        c.execute("UPDATE workers SET fraud_score=?, risk_label=? WHERE email=?",
                  (score, label, email.lower().strip()))

def update_claim_status(email: str, status: str):
    with get_conn() as c:
        c.execute("UPDATE workers SET claim_status=? WHERE email=?",
                  (status, email.lower().strip()))

def is_fraud_ring(device_id: str, worker_db_id: int) -> bool:
    if not device_id: return False
    with get_conn() as c:
        r = c.execute(
            "SELECT COUNT(DISTINCT worker_id) as cnt FROM device_registry WHERE device_id=? AND worker_id!=?",
            (device_id, str(worker_db_id))
        ).fetchone()
    return (r["cnt"] if r else 0) > 0

# ── Claims ────────────────────────────────────────────────────────

def create_claim(data: dict) -> int:
    with get_conn() as c:
        cur = c.execute(
            """INSERT INTO claims
               (worker_id,lost_hours,predicted_loss,payout,trigger_type,trigger_sources,
                aqi_value,congestion_index,weather_match,fraud_score,fraud_type,
                rules_hit,status,rejection_reasons)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["worker_id"], data.get("lost_hours",0), data.get("predicted_loss",0),
             data.get("payout",0),
             data.get("trigger_type", data.get("weather_event","")),
             data.get("trigger_sources", data.get("weather_event","")),
             data.get("aqi_value", 0),
             data.get("congestion_index", 0.0),
             data.get("weather_match",0), data.get("fraud_score",0),
             data.get("fraud_type",""), data.get("rules_hit",""),
             data.get("status","pending"), data.get("rejection_reasons",""))
        )
        return cur.lastrowid

def get_worker_claims(email: str):
    w = get_worker_by_email(email)
    if not w: return []
    with get_conn() as c:
        return c.execute(
            "SELECT * FROM claims WHERE worker_id=? ORDER BY claim_date DESC",
            (str(w["id"]),)
        ).fetchall()

def count_claims_this_week(email: str) -> int:
    w = get_worker_by_email(email)
    if not w: return 0
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    with get_conn() as c:
        r = c.execute(
            "SELECT COUNT(*) as cnt FROM claims WHERE worker_id=? AND claim_date>=?",
            (str(w["id"]), week_ago)
        ).fetchone()
    return r["cnt"] if r else 0

# ── Admin stats ───────────────────────────────────────────────────

def admin_stats() -> dict:
    with get_conn() as c:
        tw   = c.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
        ev   = c.execute("SELECT COUNT(*) FROM workers WHERE email_verified=1").fetchone()[0]
        sub  = c.execute("SELECT COUNT(*) FROM workers WHERE payment_status='SUCCESS'").fetchone()[0]
        tc   = c.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        frd  = c.execute("SELECT COUNT(*) FROM claims WHERE status='rejected'").fetchone()[0]
        appr = c.execute("SELECT COUNT(*) FROM claims WHERE status='approved'").fetchone()[0]
        rev  = c.execute("SELECT COUNT(*) FROM claims WHERE status='review'").fetchone()[0]
        pay  = c.execute("SELECT COALESCE(SUM(payout),0) FROM claims WHERE status='approved'").fetchone()[0]
        pd   = c.execute("SELECT COUNT(*) FROM workers WHERE doc_status='pending'").fetchone()[0]
        ad   = c.execute("SELECT COUNT(*) FROM workers WHERE doc_status='approved'").fetchone()[0]
        rd   = c.execute("SELECT COUNT(*) FROM workers WHERE doc_status='rejected'").fetchone()[0]
        rw   = c.execute("SELECT * FROM workers ORDER BY created_at DESC LIMIT 10").fetchall()
        rc   = c.execute("SELECT * FROM claims ORDER BY claim_date DESC LIMIT 10").fetchall()
        rings = c.execute(
            "SELECT COUNT(*) FROM (SELECT device_id FROM device_registry GROUP BY device_id HAVING COUNT(DISTINCT worker_id)>1)"
        ).fetchone()[0]
        # Trigger source breakdown
        trig_rows = c.execute(
            "SELECT trigger_type, COUNT(*) as cnt FROM claims WHERE trigger_type!='' GROUP BY trigger_type ORDER BY cnt DESC"
        ).fetchall()
        trigger_stats = {r["trigger_type"]: r["cnt"] for r in trig_rows}
    return dict(
        total_workers=tw, email_verified=ev, active_subs=sub,
        total_claims=tc, fraud_cases=frd, approved_cases=appr, review_cases=rev,
        total_payout=round(float(pay),2),
        pending_docs=pd, approved_docs=ad, rejected_docs=rd,
        fraud_rings=rings,
        trigger_stats=trigger_stats,
        recent_workers=[dict(r) for r in rw],
        recent_claims=[dict(r) for r in rc],
    )

# ── Trust Score ───────────────────────────────────────────────────

TRUST_SCORE_MAX   = 100
TRUST_SCORE_MIN   = 0
TRUST_FRAUD_DEBIT = 15   # deducted on each fraud/reject event
TRUST_CLEAN_CREDIT = 5   # added on each approved claim

def get_trust_score(email: str) -> int:
    with get_conn() as c:
        r = c.execute(
            "SELECT trust_score FROM workers WHERE email=?",
            (email.lower().strip(),)
        ).fetchone()
    return int(r["trust_score"]) if r and r["trust_score"] is not None else 100

def update_trust_score(email: str, delta: int) -> int:
    """
    Adjust trust_score by delta (positive = increase, negative = decrease).
    Clamps to [TRUST_SCORE_MIN, TRUST_SCORE_MAX].
    Returns new score.
    """
    current = get_trust_score(email)
    new_score = max(TRUST_SCORE_MIN, min(TRUST_SCORE_MAX, current + delta))
    with get_conn() as c:
        c.execute(
            "UPDATE workers SET trust_score=? WHERE email=?",
            (new_score, email.lower().strip())
        )
    return new_score

def apply_trust_penalty(email: str) -> int:
    """Deduct trust points after a fraud/rejected event."""
    return update_trust_score(email, -TRUST_FRAUD_DEBIT)

def apply_trust_reward(email: str) -> int:
    """Award trust points after a clean approved claim."""
    return update_trust_score(email, +TRUST_CLEAN_CREDIT)

def is_trust_too_low(email: str, threshold: int = 40) -> bool:
    """Return True if worker's trust score is below threshold."""
    return get_trust_score(email) < threshold

# ── Fraud Log ─────────────────────────────────────────────────────

def log_fraud_event(data: dict) -> int:
    """
    Write one row to fraud_log.

    data keys:
        worker_id, email, claim_id, event_type,
        rule_status, ml_label, ml_prob, risk_score,
        rules_hit, reason, trust_score_before, trust_score_after
    """
    with get_conn() as c:
        cur = c.execute(
            """INSERT INTO fraud_log
               (worker_id,email,claim_id,event_type,rule_status,
                ml_label,ml_prob,risk_score,rules_hit,reason,
                trust_score_before,trust_score_after)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(data.get("worker_id",   "")),
                str(data.get("email",       "")),
                int(data.get("claim_id",    0)),
                str(data.get("event_type",  "UNKNOWN")),
                str(data.get("rule_status", "")),
                int(data.get("ml_label",    0)),
                float(data.get("ml_prob",   0)),
                float(data.get("risk_score",0)),
                str(data.get("rules_hit",   "")),
                str(data.get("reason",      "")),
                int(data.get("trust_score_before", 100)),
                int(data.get("trust_score_after",  100)),
            )
        )
        return cur.lastrowid

def get_fraud_log(limit: int = 50) -> list:
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM fraud_log ORDER BY logged_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

def get_fraud_rings() -> list:
    """Return list of device_ids shared across >1 worker account."""
    with get_conn() as c:
        rows = c.execute(
            """SELECT dr.device_id,
                      COUNT(DISTINCT dr.worker_id) as account_count,
                      GROUP_CONCAT(w.email, ', ') as emails
               FROM device_registry dr
               JOIN workers w ON w.id = CAST(dr.worker_id AS INTEGER)
               GROUP BY dr.device_id
               HAVING account_count > 1
               ORDER BY account_count DESC"""
        ).fetchall()
    return [dict(r) for r in rows]

def get_suspicious_workers() -> list:
    """Return workers with trust_score < 50 or risk_label HIGH."""
    with get_conn() as c:
        rows = c.execute(
            """SELECT * FROM workers
               WHERE trust_score < 50 OR risk_label = 'HIGH'
               ORDER BY trust_score ASC"""
        ).fetchall()
    return [dict(r) for r in rows]

def mark_fraud_ring_workers(device_id: str):
    """Set risk_label=HIGH for all workers sharing this device_id."""
    with get_conn() as c:
        wids = c.execute(
            "SELECT worker_id FROM device_registry WHERE device_id=?", (device_id,)
        ).fetchall()
    for row in wids:
        with get_conn() as c:
            c.execute(
                "UPDATE workers SET risk_label='HIGH' WHERE id=?",
                (row["worker_id"],)
            )
