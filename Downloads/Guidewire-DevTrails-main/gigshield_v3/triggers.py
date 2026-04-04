"""
GigShield AI — triggers.py
============================
Phase 2: Public trigger API.

Exposes three named trigger functions + unified check_disruption().
All heavy logic lives in disruption_service.py — this module is the
clean interface used by routes and admin tooling.

Usage:
    from triggers import weather_trigger, pollution_trigger, traffic_trigger, check_disruption

    triggered, reason = check_disruption("Mumbai")
"""

from disruption_service import (
    check_aqi_trigger,
    check_traffic_trigger,
    check_flood_trigger,
    check_disruption as _check_disruption_full,
    calculate_premium as _calc_premium,
    get_city_risk_level,
    CITY_RISK_PROFILE,
    AQI_TRIGGER_THRESHOLD,
    TRAFFIC_TRIGGER_SCORE,
)
from weather_service import get_weather


# ── Trigger 1: Weather ────────────────────────────────────────────

def weather_trigger(city: str) -> tuple[bool, str]:
    """
    Detect heavy rain / storm / weather disruption.

    Returns
    -------
    (triggered: bool, reason: str)
    """
    info = get_weather(city)
    triggered = info.get("is_disrupted", False)
    reason = (
        f"Weather disruption: {info.get('condition', 'Unknown')} in {city}"
        if triggered
        else f"Weather clear in {city}: {info.get('condition', 'Clear')}"
    )
    return triggered, reason


# ── Trigger 2: Pollution / AQI ────────────────────────────────────

def pollution_trigger(city: str) -> tuple[bool, str]:
    """
    Detect hazardous air quality (AQI > threshold).

    Returns
    -------
    (triggered: bool, reason: str)
    """
    triggered, info = check_aqi_trigger(city)
    aqi = info["aqi"]
    reason = (
        f"Air pollution alert: AQI {aqi} exceeds safe limit ({AQI_TRIGGER_THRESHOLD}) in {city}"
        if triggered
        else f"Air quality acceptable: AQI {aqi} in {city}"
    )
    return triggered, reason


# ── Trigger 3: Traffic / Congestion ──────────────────────────────

def traffic_trigger(city: str) -> tuple[bool, str]:
    """
    Detect high traffic congestion (index > threshold).

    Returns
    -------
    (triggered: bool, reason: str)
    """
    triggered, info = check_traffic_trigger(city)
    score = info["congestion_index"]
    pct   = int(score * 100)
    reason = (
        f"Traffic congestion alert: {pct}% congestion in {city} (threshold {int(TRAFFIC_TRIGGER_SCORE*100)}%)"
        if triggered
        else f"Traffic normal: {pct}% congestion in {city}"
    )
    return triggered, reason


# ── Trigger 4: Flood (bonus) ──────────────────────────────────────

def flood_trigger(city: str) -> tuple[bool, str]:
    """
    Detect flood / disaster alert.

    Returns
    -------
    (triggered: bool, reason: str)
    """
    triggered, info = check_flood_trigger(city)
    reason = info["reason"]
    return triggered, reason


# ── Unified check ─────────────────────────────────────────────────

def check_disruption(city: str) -> tuple[bool, str]:
    """
    Run all triggers. Return (any_triggered, primary_reason).

    This is the single entry point used by the claim pipeline.

    Returns
    -------
    (triggered: bool, reason: str)

    Examples
    --------
    >>> triggered, reason = check_disruption("Mumbai")
    >>> # triggered = True, reason = "Weather disruption: Heavy Rain in Mumbai"
    """
    any_triggered, info = _check_disruption_full(city)
    return any_triggered, info["primary_reason"]


# ── Premium calculation (exact requested signature) ───────────────

def calculate_premium(city: str, claims_per_week: float = 0,
                      weather_risk: str = None) -> float:
    """
    Dynamic premium calculation.

    Parameters
    ----------
    city           : worker's city
    claims_per_week: past claim frequency (increases premium)
    weather_risk   : override risk level ('LOW'|'MEDIUM'|'HIGH')
                     If None, derived from city profile.

    Logic
    -----
    Base price: ₹40
    + High weather risk   → +₹50
    + Medium weather risk → +₹20
    + claims_per_week > 5 → +₹30
    + High-risk cities (Chennai, Mumbai, Kolkata, Delhi) → +₹20

    Returns
    -------
    float — weekly premium in ₹
    """
    HIGH_RISK_CITIES = {"chennai", "mumbai", "kolkata", "delhi"}

    base = 40.0

    # Determine risk level
    if weather_risk is None:
        weather_risk = get_city_risk_level(city)
    weather_risk = weather_risk.upper()

    if weather_risk == "HIGH":
        base += 50
    elif weather_risk == "MEDIUM":
        base += 20

    if claims_per_week > 5:
        base += 30

    if city.lower().strip() in HIGH_RISK_CITIES:
        base += 20

    return round(base, 2)
