"""
GigShield AI — Weather Service
================================
Uses OpenWeatherMap if OPENWEATHER_API_KEY env var is set.
Falls back to a deterministic city-risk mock with seasonal bias.
"""

import os, random
from datetime import datetime

API_KEY  = os.environ.get("OPENWEATHER_API_KEY", "")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

CITY_RISK = {
    "mumbai": 0.65, "delhi": 0.55, "chennai": 0.50, "kolkata": 0.60,
    "bengaluru": 0.35, "hyderabad": 0.40, "pune": 0.38,
    "ahmedabad": 0.30, "jaipur": 0.25, "lucknow": 0.45,
}

EVENTS = [
    "Heavy Rain", "Thunderstorm", "Dense Fog", "Cyclone Warning",
    "Flash Flood Alert", "Extreme Heat (>42°C)", "Severe Air Pollution (AQI>400)", "Hailstorm",
]

def _mock(city: str) -> dict:
    risk = CITY_RISK.get(city.lower().strip(), 0.30)
    if 6 <= datetime.utcnow().month <= 9:
        risk = min(risk + 0.20, 0.90)
    disrupted = random.random() < risk
    event = random.choice(EVENTS) if disrupted else "Clear"
    temp  = random.randint(20, 28) if disrupted else random.randint(18, 38)
    return dict(city=city, temperature=temp, condition=event,
                description=event, is_disrupted=disrupted, weather_match=1, source="mock")

def _live(city: str) -> dict | None:
    try:
        import urllib.request, json
        url = f"{BASE_URL}?q={city},IN&appid={API_KEY}&units=metric"
        with urllib.request.urlopen(url, timeout=4) as r:
            d = json.loads(r.read())
        cond = d["weather"][0]["main"]
        desc = d["weather"][0]["description"]
        temp = d["main"]["temp"]
        dis  = cond.lower() in {"rain","drizzle","thunderstorm","snow","fog","mist","haze","smoke","squall","tornado"}
        return dict(city=city, temperature=round(temp,1), condition=cond,
                    description=desc, is_disrupted=dis, weather_match=1, source="openweather")
    except Exception:
        return None

def get_weather(city: str) -> dict:
    if API_KEY:
        r = _live(city)
        if r: return r
    return _mock(city)

def weather_triggers_claim(city: str) -> tuple[bool, dict]:
    info = get_weather(city)
    return info["is_disrupted"], info
