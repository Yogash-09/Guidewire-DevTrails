"""
GigShield AI — ML Models
=========================
A. Income Prediction  → LinearRegression  (lost_hours → income_loss)
B. Fraud Detection    → RandomForestClassifier (6 features)
"""

import os, pickle, warnings
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, classification_report

warnings.filterwarnings("ignore")

_HERE      = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(_HERE, "models")
DATA_PATH  = os.path.join(_HERE, "data.csv")

FRAUD_FEATURES = [
    "claims_per_week",
    "avg_daily_hours",
    "gps_variance",
    "distance_travelled",
    "weather_match",
    "login_frequency",
]

def _save(obj, name):
    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(os.path.join(MODELS_DIR, name), "wb") as f:
        pickle.dump(obj, f)

def _load(name):
    path = os.path.join(MODELS_DIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing artefact: {path} — run train_model.py first.")
    with open(path, "rb") as f:
        return pickle.load(f)

# ─────────────────────────────────────────────────────────────────
# A. Income Prediction
# ─────────────────────────────────────────────────────────────────

def train_income_model(df: pd.DataFrame = None):
    if df is None:
        df = pd.read_csv(DATA_PATH)
    df = df[df["income_loss"] > 0].copy()
    X = df[["lost_hours"]].values
    y = df["income_loss"].values
    model = LinearRegression()
    model.fit(X, y)
    mae = mean_absolute_error(y, model.predict(X))
    _save(model, "income_model.pkl")
    print(f"[Income Model] coef=₹{model.coef_[0]:.2f}/hr  intercept={model.intercept_:.2f}  MAE=₹{mae:.2f}")
    return model

def predict_income_loss(lost_hours: float) -> float:
    try:
        m = _load("income_model.pkl")
        return round(float(m.predict([[max(0.0, float(lost_hours))]])[0]), 2)
    except Exception:
        return round(float(lost_hours) * 90.0, 2)

def get_income_chart_data():
    hours = list(range(0, 11))
    return hours, [predict_income_loss(h) for h in hours]

# ─────────────────────────────────────────────────────────────────
# B. Fraud Detection
# ─────────────────────────────────────────────────────────────────

def train_fraud_model(df: pd.DataFrame = None):
    if df is None:
        df = pd.read_csv(DATA_PATH)

    X = df[FRAUD_FEATURES].values.astype(float)
    y = df["fraud"].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_tr, X_te, y_tr, y_te = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=300, max_depth=12, min_samples_leaf=2,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    clf.fit(X_tr, y_tr)
    y_pred = clf.predict(X_te)
    print("[Fraud Model] Report:")
    print(classification_report(y_te, y_pred, target_names=["Legit","Fraud"]))
    print("Feature importances:")
    for n, i in sorted(zip(FRAUD_FEATURES, clf.feature_importances_), key=lambda x:-x[1]):
        print(f"  {n:<25} {i:.4f}")

    _save(clf,    "fraud_rf.pkl")
    _save(scaler, "fraud_scaler.pkl")
    return clf, scaler

def _load_fraud():
    return _load("fraud_rf.pkl"), _load("fraud_scaler.pkl")

# ─────────────────────────────────────────────────────────────────
# Rule Engine
# ─────────────────────────────────────────────────────────────────

class RuleEngine:
    MAX_CLAIMS_WEEK      = 8
    GPS_SPOOF_THRESHOLD  = 3000.0
    MIN_DIST_KM          = 2.0
    MAX_LOGIN_FREQ       = 20

    PENALTIES = dict(
        no_subscription  = 1.00,
        weather_mismatch = 0.35,
        too_many_claims  = 0.30,
        gps_high_var     = 0.40,
        gps_static       = 0.22,
        high_login_freq  = 0.15,
        fraud_ring       = 0.50,
    )

    @classmethod
    def evaluate(cls, claim: dict) -> dict:
        hits, reasons, penalty, auto = [], [], 0.0, False

        cpw  = float(claim.get("claims_per_week",    0))
        gpv  = float(claim.get("gps_variance",       0))
        wm   = int(  claim.get("weather_match",       1))
        dist = float(claim.get("distance_travelled",  0))
        lf   = float(claim.get("login_frequency",     1))
        sub  = bool( claim.get("has_subscription", False))
        ring = bool( claim.get("is_fraud_ring",    False))

        if not sub:
            hits.append("NO_SUBSCRIPTION")
            reasons.append("No active subscription on this account.")
            penalty += cls.PENALTIES["no_subscription"]; auto = True

        if wm == 0:
            hits.append("WEATHER_MISMATCH")
            reasons.append("Reported weather does not match official data.")
            penalty += cls.PENALTIES["weather_mismatch"]

        if cpw > cls.MAX_CLAIMS_WEEK:
            hits.append("TOO_MANY_CLAIMS")
            reasons.append(f"Claims/week ({int(cpw)}) exceeds limit of {cls.MAX_CLAIMS_WEEK}.")
            penalty += cls.PENALTIES["too_many_claims"]

        if gpv > cls.GPS_SPOOF_THRESHOLD:
            hits.append("GPS_SPOOF")
            reasons.append(f"GPS variance ({gpv:.0f} m²) indicates location spoofing.")
            penalty += cls.PENALTIES["gps_high_var"]

        if dist < cls.MIN_DIST_KM and cpw > 1:
            hits.append("GPS_STATIC")
            reasons.append(f"Distance ({dist:.1f} km) implausibly low for {int(cpw)} claims.")
            penalty += cls.PENALTIES["gps_static"]

        if lf > cls.MAX_LOGIN_FREQ:
            hits.append("HIGH_LOGIN_FREQ")
            reasons.append(f"Login frequency ({int(lf)}/day) is abnormally high.")
            penalty += cls.PENALTIES["high_login_freq"]

        if ring:
            hits.append("FRAUD_RING_DETECTED")
            reasons.append("Multiple accounts sharing the same device ID (fraud ring).")
            penalty += cls.PENALTIES["fraud_ring"]; auto = True

        return dict(rules_hit=hits, reasons=reasons,
                    penalty=round(penalty, 4), auto_reject=auto)

# ─────────────────────────────────────────────────────────────────
# Fraud Detector (ML + Rules fused)
# ─────────────────────────────────────────────────────────────────

class FraudDetector:
    ML_W = 0.55; RULE_W = 0.45; THRESHOLD = 0.50

    def __init__(self):
        self.clf, self.scaler = _load_fraud()

    def predict(self, claim: dict) -> dict:
        rules   = RuleEngine.evaluate(claim)
        ml_prob = self._ml_prob(claim)
        raw     = self.ML_W * ml_prob + self.RULE_W * min(rules["penalty"], 1.0)
        score   = round(min(raw, 1.0), 4)

        if rules["auto_reject"] or score >= self.THRESHOLD:
            decision, is_fraud = "REJECTED", True
        elif score >= 0.35:
            decision, is_fraud = "REVIEW", False
        else:
            decision, is_fraud = "APPROVED", False

        gap = abs(score - self.THRESHOLD)
        conf = "HIGH" if gap >= 0.25 else ("MEDIUM" if gap >= 0.10 else "LOW")
        return dict(ml_prob=round(ml_prob,4), rule_penalty=rules["penalty"],
                    risk_score=score, is_fraud=is_fraud, decision=decision,
                    rules_hit=rules["rules_hit"], reasons=rules["reasons"], confidence=conf)

    def _ml_prob(self, claim: dict) -> float:
        row = np.array([[
            float(claim.get("claims_per_week",    0)),
            float(claim.get("avg_daily_hours",    6)),
            float(claim.get("gps_variance",       0)),
            float(claim.get("distance_travelled", 0)),
            float(claim.get("weather_match",      1)),
            float(claim.get("login_frequency",    1)),
        ]])
        return float(self.clf.predict_proba(self.scaler.transform(row))[0][1])

# ─────────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────────

_det_cache = None

def get_detector() -> FraudDetector:
    global _det_cache
    if _det_cache is None:
        _det_cache = FraudDetector()
    return _det_cache

def check_fraud(claim: dict) -> dict:
    return get_detector().predict(claim)

def ensure_models_trained():
    needed = ["income_model.pkl", "fraud_rf.pkl", "fraud_scaler.pkl"]
    if not all(os.path.exists(os.path.join(MODELS_DIR, f)) for f in needed):
        print("[GigShield] Training ML models …")
        df = pd.read_csv(DATA_PATH)
        train_income_model(df)
        train_fraud_model(df)
        print("[GigShield] Models ready.")
    else:
        print("[GigShield] ML models already trained.")
