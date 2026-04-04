"""
GigShield AI — Email OTP Service (FREE)
=========================================
Sends OTP to worker's email via Gmail SMTP.
Falls back to console print in dev mode.

Setup (one-time, 2 minutes):
  1. Enable 2-Step Verification on your Google account
  2. myaccount.google.com → Security → App Passwords → create one
  3. Add to .env:
       GMAIL_USER=youremail@gmail.com
       GMAIL_PASS=xxxx xxxx xxxx xxxx

No Twilio. No paid service. Completely free.
"""

import os, random, string, sqlite3
from datetime import datetime, timedelta

# Load .env so GMAIL_USER / GMAIL_PASS are available
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    print("[OTP] .env loaded")
except ImportError:
    pass

OTP_EXPIRY_MINUTES  = 10
OTP_LENGTH          = 6
MAX_ATTEMPTS_WINDOW = 15
MAX_ATTEMPTS        = 5

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gigshield.db")

EMAIL_SUBJECT = "GigShield AI — Your Email Verification OTP"

EMAIL_HTML = """\
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#f7f5f0;padding:32px">
  <div style="max-width:460px;margin:auto;background:#fff;border-radius:16px;padding:32px;box-shadow:0 4px 20px rgba(0,0,0,.08)">
    <h2 style="color:#0a0e1a;margin:0 0 4px">GigShield AI 🛡️</h2>
    <p style="color:#6b7280;font-size:14px;margin:0 0 24px">Email Verification</p>

    <p style="color:#374151;font-size:15px">Hello <strong>{name}</strong>,</p>
    <p style="color:#374151;font-size:14px">Your one-time verification code is:</p>

    <div style="background:#f0fdf4;border:2px solid #00c9a7;border-radius:12px;padding:20px;text-align:center;margin:20px 0">
      <span style="font-size:36px;font-weight:800;letter-spacing:10px;color:#0a0e1a">{otp}</span>
    </div>

    <p style="color:#6b7280;font-size:13px">
      ⏱ Valid for <strong>{expiry} minutes</strong> &nbsp;·&nbsp;
      🔒 Do NOT share this with anyone
    </p>

    <hr style="border:none;border-top:1px solid #f3f4f6;margin:20px 0"/>

    <p style="color:#9ca3af;font-size:12px">
      <strong>Important:</strong> This OTP verifies your email address only.
      Your platform affiliation (Swiggy / Zomato) is self-declared and will be
      reviewed by our admin team after you upload your identity documents.
    </p>
  </div>
</body>
</html>"""

EMAIL_TEXT = """\
Hello {name},

Your GigShield AI verification OTP is: {otp}

Valid for {expiry} minutes. Do NOT share it with anyone.

Note: This verifies your email only. Platform affiliation is self-declared
and will be reviewed by admin after document upload.

— GigShield AI Team
"""

# ── DB helpers ────────────────────────────────────────────────────

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def _ensure_table():
    with _conn() as c:
        c.execute("""
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
            )
        """)

_ensure_table()

# Startup: confirm Gmail credentials are loaded
def _check_gmail_config():
    user = os.environ.get("GMAIL_USER", "").strip()
    pwd  = os.environ.get("GMAIL_PASS", "").strip()
    if user and pwd and user != "your_email@gmail.com":
        print(f"[OTP] Gmail ready -> {user}")
    else:
        print("[OTP] Gmail not configured -- OTP printing to console")
        print("[OTP]    Fix: add GMAIL_USER and GMAIL_PASS to .env")

_check_gmail_config()

# ── Core functions ────────────────────────────────────────────────

def generate_otp() -> str:
    return "".join(random.choices(string.digits, k=OTP_LENGTH))

def _rate_ok(email: str) -> tuple[bool, str]:
    window = (datetime.utcnow() - timedelta(minutes=MAX_ATTEMPTS_WINDOW)).isoformat()
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS cnt FROM otp_log WHERE email=? AND created_at>=?",
            (email.lower(), window)
        ).fetchone()
    if (row["cnt"] if row else 0) >= MAX_ATTEMPTS:
        return False, f"Too many OTP requests. Wait {MAX_ATTEMPTS_WINDOW} min."
    return True, ""

def _log_otp(email, otp, worker_id, delivered, channel):
    exp = (datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO otp_log (email,otp,worker_id,expires_at,delivered,channel) VALUES (?,?,?,?,?,?)",
            (email.lower(), otp, worker_id, exp, int(delivered), channel)
        )

def _gmail(to_email: str, otp: str, name: str) -> tuple[bool, str]:
    user = os.environ.get("GMAIL_USER", "").strip()
    pwd  = os.environ.get("GMAIL_PASS", "").strip().replace(" ", "")
    if not (user and pwd):
        return False, "gmail_not_configured"

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg["Subject"] = EMAIL_SUBJECT
    msg["From"]    = f"GigShield AI <{user}>"
    msg["To"]      = to_email

    ctx = {"name": name, "otp": otp, "expiry": OTP_EXPIRY_MINUTES}
    msg.attach(MIMEText(EMAIL_TEXT.format(**ctx), "plain"))
    msg.attach(MIMEText(EMAIL_HTML.format(**ctx), "html"))

    last_error = ""

    # Try port 587 STARTTLS
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, pwd)
            smtp.sendmail(user, [to_email], msg.as_string())
        print(f"[OTP] Email sent via port 587 -> {to_email}")
        return True, "sent"
    except Exception as e:
        last_error = str(e)
        print(f"[OTP] Port 587 failed -> {last_error} (trying 465...)")

    # Fall back to port 465 SSL
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(user, pwd)
            smtp.sendmail(user, [to_email], msg.as_string())
        print(f"[OTP] Email sent via port 465 -> {to_email}")
        return True, "sent"
    except Exception as e:
        last_error = str(e)
        print(f"[OTP] Port 465 failed -> {last_error}")

    print(f"[OTP] Both ports failed. Last error: {last_error}")
    return False, last_error

def _console_fallback(email: str, otp: str):
    print()
    print("=" * 56)
    print("  GigShield AI -- OTP  (CONSOLE / DEV MODE)")
    print("=" * 56)
    print(f"  Email   : {email}")
    print(f"  OTP     : {otp}")
    print(f"  Expires : {OTP_EXPIRY_MINUTES} minutes")
    print()
    print("  Set GMAIL_USER + GMAIL_PASS to send real emails")
    print("=" * 56)
    print()

# ── Public API ────────────────────────────────────────────────────

def send_otp(email: str, otp: str, worker_id: str = "", name: str = "Worker") -> dict:
    """
    Send OTP to email. Returns result dict with channel info.
    """
    email = email.lower().strip()

    ok, msg = _rate_ok(email)
    if not ok:
        return {"success": False, "channel": "blocked", "message": msg}

    # Try Gmail
    delivered, detail = _gmail(email, otp, name)
    if delivered:
        _log_otp(email, otp, worker_id, True, "email")
        return {
            "success": True,
            "channel": "email",
            "message": f"OTP sent to {email}. Check your inbox.",
            "debug_otp": "",
        }

    # Console fallback
    _console_fallback(email, otp)
    _log_otp(email, otp, worker_id, False, "console")

    warning = (
        "Gmail not configured. Set GMAIL_USER + GMAIL_PASS in .env to send real emails."
        if detail == "gmail_not_configured"
        else f"Gmail failed: {detail}"
    )
    return {
        "success": True,
        "channel": "console",
        "message": "OTP generated. Configure Gmail to send real emails.",
        "debug_otp": otp,   # shown on-screen in dev mode only
        "warning": warning,
    }

def verify_otp_expiry(email: str, entered: str) -> tuple[bool, str]:
    """Check OTP is valid and not expired."""
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        row = c.execute(
            "SELECT id, otp, expires_at FROM otp_log WHERE email=? AND used=0 ORDER BY created_at DESC LIMIT 1",
            (email.lower(),)
        ).fetchone()
    if not row:
        return False, "No OTP found. Please request a new one."
    if row["expires_at"] < now:
        return False, "OTP expired. Please request a new one."
    if str(row["otp"]).strip() != str(entered).strip():
        return False, "Incorrect OTP. Please try again."
    with _conn() as c:
        c.execute("UPDATE otp_log SET used=1 WHERE id=?", (row["id"],))
    return True, "OTP verified."


# ── Phone OTP (console fallback — plug in Twilio/MSG91 here) ──────

def send_otp_phone(phone: str, otp: str) -> dict:
    """
    Send OTP to a phone number.
    Currently prints to console. Replace _sms() body with your SMS provider.
    """
    print()
    print("=" * 50)
    print("  GigShield AI — PHONE OTP (CONSOLE / DEV MODE)")
    print("=" * 50)
    print(f"  📱 Phone : {phone}")
    print(f"  🔑 OTP   : {otp}")
    print(f"  ⏱  Valid : {OTP_EXPIRY_MINUTES} minutes")
    print("=" * 50)
    print()
    return {
        "success": True,
        "channel": "console",
        "message": "OTP generated. Check terminal (SMS not configured).",
    }


def send_email(to_email: str, subject: str, message: str) -> bool:
    """
    Reusable email sender for reminders / alerts.
    Returns True on success, False on failure (falls back to console print).
    """
    user = os.environ.get("GMAIL_USER", "").strip()
    pwd  = os.environ.get("GMAIL_PASS", "").strip().replace(" ", "")

    if not (user and pwd):
        print(f"[EMAIL] (console fallback) To: {to_email} | Subject: {subject}\n{message}")
        return False

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"GigShield AI <{user}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(message, "plain"))

    for port, use_ssl in [(587, False), (465, True)]:
        try:
            if use_ssl:
                with smtplib.SMTP_SSL("smtp.gmail.com", port, timeout=15) as smtp:
                    smtp.login(user, pwd)
                    smtp.sendmail(user, [to_email], msg.as_string())
            else:
                with smtplib.SMTP("smtp.gmail.com", port, timeout=15) as smtp:
                    smtp.ehlo(); smtp.starttls(); smtp.ehlo()
                    smtp.login(user, pwd)
                    smtp.sendmail(user, [to_email], msg.as_string())
            print(f"[EMAIL] Sent -> {to_email} | {subject}")
            return True
        except Exception as e:
            print(f"[EMAIL] Port {port} failed: {e}")

    print(f"[EMAIL] (console fallback) To: {to_email} | Subject: {subject}\n{message}")
    return False
