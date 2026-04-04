"""
GigShield AI — disruption_service.py
======================================
Phase 2: Multi-source disruption detection + dynamic premium calculation.

Trigger sources:
  1. Weather       — OpenWeatherMap (existing weather_service)
  2. Air Quality   — WAQI API or mock AQI by city
  3. Traffic       — mock congestion model (pluggable)
  4. Flood/Disaster— mock alert layer

Premium calculation:
  calculate_premium(city, risk_level, claim_history) → float (₹/week)
"""

import os, random
from datetime import datetime
from weather_service import get_weather

# ── City risk profiles ────────────────────────────────────────────
# Composite score 0–1 based on historical weather, AQI, flood risk
CITY_RISK_PROFILE = {
    "mumbai":    {"weather": 0.75, "aqi": 0.55, "traffic": 0.70, "flood": 0.65},
    "delhi":     {"weather": 0.50, "aqi": 0.90, "traffic": 0.85, "flood": 0.40},
    "chennai":   {"weather": 0.60, "aqi": 0.45, "traffic": 0.60, "flood": 0.55},
    "kolkata":   {"weather": 0.65, "aqi": 0.60, "traffic": 0.65, "flood": 0.70},
    "bengaluru": {"weather": 0.40, "aqi": 0.40, "traffic": 0.75, "flood": 0.20},
    "hyderabad": {"weather": 0.45, "aqi": 0.45, "traffic": 0.55, "flood": 0.35},
    "pune":      {"weather": 0.42, "aqi": 0.38, "traffic": 0.50, "flood": 0.30},
    "ahmedabad": {"weather": 0.30, "aqi": 0.55, "traffic": 0.45, "flood": 0.25},
    "jaipur":    {"weather": 0.28, "aqi": 0.50, "traffic": 0.40, "flood": 0.20},
    "lucknow":   {"weather": 0.48, "aqi": 0.65, "traffic": 0.50, "flood": 0.45},
}

_DEFAULT_PROFILE = {"weather": 0.35, "aqi": 0.40, "traffic": 0.45, "flood": 0.30}

AQI_API_KEY = os.environ.get("WAQI_API_KEY", "")
AQI_TRIGGER_THRESHOLD   = 150   # Unhealthy for sensitive groups
TRAFFIC_TRIGGER_SCORE   = 0.65  # 0–1 congestion index


# ── 1. AQI Trigger ────────────────────────────────────────────────

def _get_aqi_live(city: str) -> dict | None:
    """Fetch real AQI from WAQI API if key is configured."""
    if not AQI_API_KEY:
        return None
    try:
        import urllib.request, json
        url = f"https://api.waqi.info/feed/{city}/?token={AQI_API_KEY}"
        with urllib.request.urlopen(url, timeout=4) as r:
            d = json.loads(r.read())
        if d.get("status") != "ok":
            return None
        aqi = int(d["data"]["aqi"])
        return {"aqi": aqi, "source": "waqi"}
    except Exception:
        return None


def _get_aqi_mock(city: str) -> dict:
    """Deterministic mock AQI based on city risk profile + seasonal bias."""
    profile = CITY_RISK_PROFILE.get(city.lower().strip(), _DEFAULT_PROFILE)
    base    = profile["aqi"] * 300          # scale 0–300
    # Winter months (Nov–Feb) → higher AQI for north Indian cities
    month = datetime.utcnow().month
    if month in (11, 12, 1, 2) and city.lower() in ("delhi", "lucknow", "jaipur"):
        base = min(base * 1.6, 500)
    aqi = int(base + random.uniform(-20, 20))
    return {"aqi": max(0, aqi), "source": "mock"}


def check_aqi_trigger(city: str) -> tuple[bool, dict]:
    """
    Returns (triggered: bool, info: dict).
    Triggered when AQI > AQI_TRIGGER_THRESHOLD.
    """
    data = _get_aqi_live(city) or _get_aqi_mock(city)
    aqi  = data["aqi"]
    triggered = aqi > AQI_TRIGGER_THRESHOLD
    return triggered, {
        "trigger_type": "AQI",
        "aqi":          aqi,
        "threshold":    AQI_TRIGGER_THRESHOLD,
        "triggered":    triggered,
        "reason":       f"Air Quality Index {aqi} exceeds safe threshold ({AQI_TRIGGER_THRESHOLD})" if triggered else f"AQI {aqi} — within safe range",
        "source":       data["source"],
    }


# ── 2. Traffic / Congestion Trigger ──────────────────────────────

def _get_traffic_mock(city: str) -> dict:
    """Mock traffic congestion index 0–1 based on city profile + time of day."""
    profile = CITY_RISK_PROFILE.get(city.lower().strip(), _DEFAULT_PROFILE)
    base    = profile["traffic"]
    hour    = datetime.utcnow().hour
    # Peak hours: 8–10 AM and 5–8 PM IST (UTC+5:30 → UTC 2:30–4:30 and 11:30–14:30)
    if hour in (3, 4, 11, 12, 13):
        base = min(base + 0.20, 1.0)
    score = round(base + random.uniform(-0.10, 0.10), 3)
    return {"congestion_index": max(0.0, min(1.0, score)), "source": "mock"}


def check_traffic_trigger(city: str) -> tuple[bool, dict]:
    """
    Returns (triggered: bool, info: dict).
    Triggered when congestion_index > TRAFFIC_TRIGGER_SCORE.
    """
    data  = _get_traffic_mock(city)
    score = data["congestion_index"]
    triggered = score > TRAFFIC_TRIGGER_SCORE
    return triggered, {
        "trigger_type":      "TRAFFIC",
        "congestion_index":  round(score, 3),
        "threshold":         TRAFFIC_TRIGGER_SCORE,
        "triggered":         triggered,
        "reason":            f"High traffic congestion ({score:.0%}) detected in {city}" if triggered else f"Traffic normal ({score:.0%})",
        "source":            data["source"],
    }


# ── 3. Flood / Disaster Alert (mock) ─────────────────────────────

def check_flood_trigger(city: str) -> tuple[bool, dict]:
    """
    Mock flood/disaster alert based on city flood risk + monsoon season.
    """
    profile  = CITY_RISK_PROFILE.get(city.lower().strip(), _DEFAULT_PROFILE)
    base     = profile["flood"]
    month    = datetime.utcnow().month
    if 6 <= month <= 9:          # monsoon season
        base = min(base + 0.25, 1.0)
    triggered = random.random() < (base * 0.4)   # lower probability than weather
    return triggered, {
        "trigger_type": "FLOOD",
        "triggered":    triggered,
        "reason":       f"Flood/disaster alert active in {city}" if triggered else f"No flood alert for {city}",
        "source":       "mock",
    }


# ── 4. Unified Disruption Check ───────────────────────────────────

def check_disruption(city: str) -> tuple[bool, dict]:
    """
    Run all 4 trigger sources. Return (any_triggered, combined_result).

    Returns
    -------
    triggered : bool
    result    : dict with keys:
        triggered, triggers_fired, primary_reason,
        weather, aqi, traffic, flood
    """
    city = city.strip()

    weather_info = get_weather(city)
    weather_trig = weather_info.get("is_disrupted", False)

    aqi_trig,     aqi_info     = check_aqi_trigger(city)
    traffic_trig, traffic_info = check_traffic_trigger(city)
    flood_trig,   flood_info   = check_flood_trigger(city)

    any_triggered = weather_trig or aqi_trig or traffic_trig or flood_trig

    fired = []
    if weather_trig: fired.append("WEATHER")
    if aqi_trig:     fired.append("AQI")
    if traffic_trig: fired.append("TRAFFIC")
    if flood_trig:   fired.append("FLOOD")

    # Primary reason = first fired trigger
    if weather_trig:
        primary = f"Weather: {weather_info.get('condition', 'Disruption')}"
    elif aqi_trig:
        primary = aqi_info["reason"]
    elif traffic_trig:
        primary = traffic_info["reason"]
    elif flood_trig:
        primary = flood_info["reason"]
    else:
        primary = "No disruption detected"

    return any_triggered, {
        "triggered":       any_triggered,
        "triggers_fired":  fired,
        "trigger_count":   len(fired),
        "primary_reason":  primary,
        "weather":         weather_info,
        "aqi":             aqi_info,
        "traffic":         traffic_info,
        "flood":           flood_info,
    }


# ── 5. Dynamic Premium Calculation ───────────────────────────────

# Premium bands (₹/week)
PREMIUM_BANDS = {
    "LOW":    (30,  50),
    "MEDIUM": (60,  90),
    "HIGH":   (100, 150),
}

def calculate_premium(city: str, risk_level: str = None, claim_history: int = 0) -> float:
    """
    AI-based dynamic premium calculation.

    Parameters
    ----------
    city          : worker's city
    risk_level    : override ('LOW'|'MEDIUM'|'HIGH'). If None, computed from city profile.
    claim_history : number of past claims (increases premium)

    Returns
    -------
    float — weekly premium in ₹
    """
    profile = CITY_RISK_PROFILE.get(city.lower().strip(), _DEFAULT_PROFILE)

    # Composite city risk score (weighted average of all factors)
    city_score = (
        profile["weather"] * 0.40 +
        profile["aqi"]     * 0.25 +
        profile["traffic"] * 0.20 +
        profile["flood"]   * 0.15
    )

    # Determine risk tier from city score if not overridden
    if risk_level is None:
        if city_score >= 0.55:
            risk_level = "HIGH"
        elif city_score >= 0.38:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

    risk_level = risk_level.upper()
    lo, hi = PREMIUM_BANDS.get(risk_level, PREMIUM_BANDS["MEDIUM"])

    # Base premium = interpolate within band using city_score
    band_range = hi - lo
    # Normalise city_score to 0–1 within the band
    if risk_level == "LOW":
        t = min(city_score / 0.38, 1.0)
    elif risk_level == "MEDIUM":
        t = min((city_score - 0.38) / 0.17, 1.0)
    else:
        t = min((city_score - 0.55) / 0.45, 1.0)

    base_premium = lo + t * band_range

    # Claim history loading: +5% per past claim, capped at +40%
    loading = min(claim_history * 0.05, 0.40)
    premium = base_premium * (1 + loading)

    return round(max(lo, min(hi, premium)), 2)


def get_city_risk_level(city: str) -> str:
    """Return LOW / MEDIUM / HIGH risk label for a city."""
    profile = CITY_RISK_PROFILE.get(city.lower().strip(), _DEFAULT_PROFILE)
    score   = (
        profile["weather"] * 0.40 +
        profile["aqi"]     * 0.25 +
        profile["traffic"] * 0.20 +
        profile["flood"]   * 0.15
    )
    if score >= 0.55: return "HIGH"
    if score >= 0.38: return "MEDIUM"
    return "LOW"
