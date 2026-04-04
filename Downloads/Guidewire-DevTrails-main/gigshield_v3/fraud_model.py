"""
GigShield AI — fraud_model.py
================================
Standalone fraud prediction interface.
Loads the trained RandomForestClassifier from models/fraud_rf.pkl.

This module is the clean public API for fraud scoring.
The heavy training logic lives in ml_model.py / train_model.py.

Usage:
    from fraud_model import predict_fraud, fraud_probability

    result = predict_fraud(
        claims=4, hours=6.5, gps=120.0,
        distance=85.0, weather=1, login=3
    )
    # returns 0 (genuine) or 1 (fraud)
"""

import os, pickle, logging
import numpy as np

_HERE      = os.path.dirname(os.path.abspath(__file__))
_MODEL_DIR = os.path.join(_HERE, "models")

logger = logging.getLogger("gigshield.fraud_model")

# Feature order must match training (ml_model.py FRAUD_FEATURES)
FEATURE_ORDER = [
    "claims_per_week",
    "avg_daily_hours",
    "gps_variance",
    "distance_travelled",
    "weather_match",
    "login_frequency",
]

_clf    = None
_scaler = None


def _load_artefacts():
    """Load model + scaler once, cache in module globals."""
    global _clf, _scaler
    if _clf is not None:
        return

    clf_path    = os.path.join(_MODEL_DIR, "fraud_rf.pkl")
    scaler_path = os.path.join(_MODEL_DIR, "fraud_scaler.pkl")

    if not os.path.exists(clf_path):
        raise FileNotFoundError(
            f"fraud_rf.pkl not found at {clf_path}\n"
            "Run:  python train_model.py  to train first."
        )

    with open(clf_path,    "rb") as f: _clf    = pickle.load(f)
    with open(scaler_path, "rb") as f: _scaler = pickle.load(f)
    logger.info("[fraud_model] Loaded fraud_rf.pkl ✅")


def predict_fraud(
    claims:   float,
    hours:    float,
    gps:      float,
    distance: float,
    weather:  int,
    login:    float,
) -> int:
    """
    Predict whether a claim is fraudulent.

    Parameters
    ----------
    claims   : claims_per_week      (int/float)
    hours    : avg_daily_hours      (float)
    gps      : gps_variance m²      (float)
    distance : distance_travelled km (float)
    weather  : weather_match        (1 = match, 0 = mismatch)
    login    : login_frequency/day  (float)

    Returns
    -------
    int
        0 = Genuine
        1 = Fraud
    """
    _load_artefacts()
    row = np.array([[
        float(claims),
        float(hours),
        float(gps),
        float(distance),
        int(weather),
        float(login),
    ]])
    scaled = _scaler.transform(row)
    result = int(_clf.predict(scaled)[0])
    logger.debug(
        "[fraud_model] predict_fraud(%s) → %s",
        dict(zip(FEATURE_ORDER, row[0])), result
    )
    return result


def fraud_probability(
    claims:   float,
    hours:    float,
    gps:      float,
    distance: float,
    weather:  int,
    login:    float,
) -> float:
    """
    Return the raw probability of fraud (0.0 – 1.0).
    Useful for nuanced risk scoring instead of binary decision.
    """
    _load_artefacts()
    row = np.array([[
        float(claims), float(hours), float(gps),
        float(distance), int(weather), float(login),
    ]])
    prob = float(_clf.predict_proba(_scaler.transform(row))[0][1])
    logger.debug("[fraud_model] fraud_probability → %.4f", prob)
    return round(prob, 4)


def predict_fraud_full(claim: dict) -> dict:
    """
    Convenience wrapper that accepts a dict (same keys as FEATURE_ORDER).
    Returns a full result dict compatible with the rest of the system.

    Parameters
    ----------
    claim : dict with keys:
        claims_per_week, avg_daily_hours, gps_variance,
        distance_travelled, weather_match, login_frequency

    Returns
    -------
    dict:
        ml_label    : int   0 or 1
        ml_prob     : float 0.0–1.0
        is_fraud    : bool
        label_str   : str   'GENUINE' or 'FRAUD'
    """
    c = claims  = float(claim.get("claims_per_week",    0))
    h = hours   = float(claim.get("avg_daily_hours",    6))
    g = gps     = float(claim.get("gps_variance",       0))
    d = dist    = float(claim.get("distance_travelled", 0))
    w = weather = int(  claim.get("weather_match",      1))
    l = login   = float(claim.get("login_frequency",    1))

    label = predict_fraud(c, h, g, d, w, l)
    prob  = fraud_probability(c, h, g, d, w, l)

    return {
        "ml_label":  label,
        "ml_prob":   prob,
        "is_fraud":  label == 1,
        "label_str": "FRAUD" if label == 1 else "GENUINE",
    }
