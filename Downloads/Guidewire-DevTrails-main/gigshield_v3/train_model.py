"""
GigShield AI — Standalone Model Trainer
========================================
Run once to train and persist both ML models.

Usage:
    python train_model.py
    python train_model.py --data path/to/custom.csv
    python train_model.py --retrain   (force retrain even if artefacts exist)
"""

import os, sys, argparse
import pandas as pd
from ml_model import (
    train_income_model, train_fraud_model,
    predict_income_loss, get_detector, MODELS_DIR, DATA_PATH,
)

def run(data_path: str, force: bool = False):
    print("=" * 58)
    print("  GigShield AI — Model Training Pipeline")
    print("=" * 58)

    # Check artefacts
    needed = ["income_model.pkl", "fraud_rf.pkl", "fraud_scaler.pkl"]
    if not force and all(os.path.exists(os.path.join(MODELS_DIR, f)) for f in needed):
        print("[INFO] Artefacts already exist. Use --retrain to overwrite.")
        return

    if not os.path.exists(data_path):
        print(f"[ERROR] Data file not found: {data_path}")
        sys.exit(1)

    df = pd.read_csv(data_path)
    print(f"\nDataset loaded: {len(df)} rows")
    print(f"  Legit  : {(df['fraud']==0).sum()}")
    print(f"  Fraud  : {(df['fraud']==1).sum()}")
    fraud_types = df[df['fraud']==1]['fraud_type'].value_counts()
    for ft, cnt in fraud_types.items():
        print(f"    └─ {ft}: {cnt}")

    print("\n── A. Income Prediction Model ─────────────────────")
    train_income_model(df)

    print("\n── B. Fraud Detection Model ───────────────────────")
    train_fraud_model(df)

    print("\n── Smoke Tests ────────────────────────────────────")
    det = get_detector()

    tests = [
        ("Legit worker",       dict(claims_per_week=2, avg_daily_hours=6, gps_variance=50, distance_travelled=120, weather_match=1, login_frequency=2, has_subscription=True, is_fraud_ring=False)),
        ("GPS spoofer",        dict(claims_per_week=18,avg_daily_hours=10,gps_variance=5000,distance_travelled=0.8,weather_match=0, login_frequency=28,has_subscription=False,is_fraud_ring=False)),
        ("Fraud ring member",  dict(claims_per_week=15,avg_daily_hours=9.7,gps_variance=3900,distance_travelled=3.2,weather_match=1,login_frequency=29,has_subscription=True, is_fraud_ring=True)),
        ("Weather mismatch",   dict(claims_per_week=10,avg_daily_hours=9.2,gps_variance=3200,distance_travelled=15,weather_match=0, login_frequency=15,has_subscription=True, is_fraud_ring=False)),
    ]
    for label, claim in tests:
        r = det.predict(claim)
        print(f"  [{label:<20}] {r['decision']:<8} score={r['risk_score']:.3f}  conf={r['confidence']}")

    print(f"\nIncome Prediction Examples:")
    for h in [1, 2, 3, 5, 8]:
        print(f"  {h} lost hours → ₹{predict_income_loss(h):.2f}")

    print("\n✅  Training complete. Artefacts saved to /models/")
    print("=" * 58)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GigShield AI Model Trainer")
    parser.add_argument("--data",    default=DATA_PATH, help="Path to training CSV")
    parser.add_argument("--retrain", action="store_true", help="Force retrain even if artefacts exist")
    args = parser.parse_args()
    run(args.data, force=args.retrain)
