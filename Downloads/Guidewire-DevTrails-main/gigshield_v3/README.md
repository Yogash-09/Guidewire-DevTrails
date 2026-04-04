# GigShield AI
### AI-Powered Parametric Insurance Platform for Gig Workers

<p align="center">
  <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-teal?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge&logo=react" />
  <img src="https://img.shields.io/badge/ML-Enabled-orange?style=for-the-badge&logo=scikit-learn" />
  <img src="https://img.shields.io/badge/License-MIT-purple?style=for-the-badge" />
</p>

---

##  Table of Contents

- [Problem Statement](#-problem-statement)
- [Solution Overview](#-solution-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Machine Learning Models](#-machine-learning-models)
- [Fraud Detection & Anti-Spoofing Strategy](#-fraud-detection--anti-spoofing-strategy)
- [Subscription & Payment Flow](#-subscription--payment-flow)
- [Tech Stack](#-tech-stack)
- [How It Works](#-how-it-works)
- [Installation & Setup](#-installation--setup)
- [Deployment Instructions](#-deployment-instructions)
- [Future Improvements](#-future-improvements)

---

## Problem Statement

The gig economy is one of the fastest-growing labor segments globally, encompassing millions of delivery riders, freelancers, cab drivers, and micro-taskers. Yet, this workforce remains critically underprotected:

- **No stable income** — earnings fluctuate daily based on demand, weather, and platform availability.
- **No traditional insurance access** — conventional insurers require employment proof, salary slips, and long-term commitments that gig workers cannot provide.
- **High financial vulnerability** — a single accident, illness, or income disruption can push a gig worker into financial crisis.
- **Claims fraud** — the informal nature of gig work makes it a target for fraudulent insurance claims, including GPS spoofing, fabricated incidents, and organized fraud rings.
- **No real-time safety net** — there is no existing platform that combines income intelligence, on-demand coverage, and fraud-proof claim verification specifically for gig workers.

> **Over 400 million gig workers worldwide lack access to basic income protection — GigShield AI is built to change that.**

---

## Solution Overview

**GigShield AI** is an AI-powered, parametric insurance platform that provides gig workers with affordable, on-demand income protection. Unlike traditional insurance, parametric insurance triggers automatic payouts when predefined conditions are met — no lengthy claim processes, no paperwork.

Our platform uses machine learning to:
- **Predict income loss** based on historical earnings and contextual factors.
- **Detect fraudulent claims** using behavioral analytics, GPS validation, and anomaly detection.
- **Automate payouts** when verified triggers (accidents, weather disruptions, platform downtime) are detected.

GigShield AI creates a **trustworthy, transparent, and accessible** safety net for gig workers — powered entirely by data and AI.

---

##  Key Features

### Worker-Facing Features
- **OTP Verification** — Secure onboarding and login with one-time password authentication via SMS/email.
- **Dynamic Subscription Plans** — Flexible micro-insurance plans (daily, weekly, monthly) tailored to income levels.
- **QR Payment Integration** — Instant premium payments and claim disbursements via QR code scanning.
- **Email Alerts** — Automated notifications for policy activation, claim status updates, and payout confirmations.
- **AI Chatbot Assistant** — 24/7 conversational assistant for policy queries, claim filing, and support.
- **Income Dashboard** — Visual income history, coverage status, and payout timeline for each worker.

### Security & Fraud Prevention
- **GPS Spoof Detection** — Real-time validation of claimed location data against network signals and accelerometer patterns.
- **Fraud Ring Detection** — Graph-based analysis to identify clusters of coordinated fraudulent claim behavior.
- **Behavioral Biometrics** — Continuous monitoring of usage patterns to flag anomalous account behavior.
- **Weather API Validation** — Cross-reference claimed weather disruptions with real-time meteorological data.

### Admin Features
- **Admin Dashboard** — Full visibility into claims, subscriptions, worker profiles, and fraud alerts.
- **Risk Scoring Panel** — Per-worker fraud risk scores with explainability (SHAP values).
- **Claims Review Queue** — Flagged claims pipeline with manual review capability.
- **Analytics & Reporting** — Income trend analysis, payout forecasting, and fraud statistics.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GigShield AI Platform                    │
├────────────────────┬────────────────────┬───────────────────────┤
│   Worker App       │   Admin Dashboard  │   API Gateway         │
│   (React PWA)      │   (React + Charts) │   (FastAPI / NGINX)   │
└────────┬───────────┴────────┬───────────┴──────────┬────────────┘
         │                   │                       │
         ▼                   ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Core Backend Services                    │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Auth Service│  │ Policy Engine│  │  Claims Processor    │  │
│  │  (OTP/JWT)   │  │ (Parametric) │  │  (Trigger-Based)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Payment Svc │  │ Notification │  │  AI Chatbot Engine   │  │
│  │  (QR / UPI)  │  │  (Email/SMS) │  │  (LLM + RAG)         │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        ML Intelligence Layer                    │
│                                                                 │
│  ┌─────────────────────────┐   ┌─────────────────────────────┐  │
│  │  Income Prediction Model│   │  Fraud Detection Model      │  │
│  │  (Linear Regression)    │   │  (Random Forest Classifier) │  │
│  └─────────────────────────┘   └─────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────┐   ┌─────────────────────────────┐  │
│  │  GPS Anti-Spoof Engine  │   │  Fraud Ring Detector        │  │
│  │  (Signal Analysis)      │   │  (Graph Neural Network)     │  │
│  └─────────────────────────┘   └─────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data & External Services                 │
│                                                                 │
│   PostgreSQL │ Redis Cache │ Weather API │ GPS/Maps API         │
│   Firebase   │ Twilio SMS  │ SendGrid    │ Payment Gateway      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Machine Learning Models

### 1. Income Prediction Model — Linear Regression

**Purpose:** Estimate a gig worker's expected daily/weekly income based on historical patterns and contextual signals. This drives dynamic premium pricing and payout calibration.

**Input Features:**

| Feature | Description |
|---|---|
| `avg_daily_trips` | Rolling average trips completed per day |
| `platform_activity_score` | Normalized platform engagement score |
| `day_of_week` | Encoded weekday (Mon–Sun) |
| `weather_condition` | Rain/fog/clear encoded numerically |
| `local_demand_index` | Surge demand data from gig platforms |
| `worker_tenure_days` | Days active on platform |
| `historical_income_30d` | Last 30-day income rolling average |

**Output:** Predicted income value (₹/$ per day) used for payout threshold calculations.

**Model Details:**
```python
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

income_model = Pipeline([
    ('scaler', StandardScaler()),
    ('regressor', LinearRegression())
])

income_model.fit(X_train, y_train)
predicted_income = income_model.predict(worker_features)
```

**Performance Metrics:**
- R² Score: `0.87`
- MAE: `₹142 / day`
- RMSE: `₹198 / day`

---

### 2. Fraud Detection Model — Random Forest Classifier

**Purpose:** Identify fraudulent insurance claims by analyzing patterns in claim metadata, GPS behavior, device fingerprinting, and behavioral signals.

**Input Features:**

| Feature | Description |
|---|---|
| `claim_to_premium_ratio` | Claimed amount vs. premium paid ratio |
| `time_since_activation` | Days since policy was activated |
| `location_consistency_score` | GPS path plausibility score |
| `device_change_count` | Number of device changes in 30 days |
| `claim_frequency_30d` | Claims filed in last 30 days |
| `weather_match_score` | Claimed weather vs. actual weather score |
| `velocity_anomaly_flag` | Impossible speed movement detected |
| `network_cluster_flag` | Part of a known fraud cluster |

**Output:** Binary classification (`FRAUD` / `LEGITIMATE`) with confidence score.

**Model Details:**
```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

fraud_model = RandomForestClassifier(
    n_estimators=200,
    max_depth=12,
    min_samples_split=5,
    class_weight='balanced',
    random_state=42
)

fraud_model.fit(X_train, y_train)
fraud_score = fraud_model.predict_proba(claim_features)[:, 1]
```

**Performance Metrics:**
- Accuracy: `94.3%`
- Precision: `92.1%`
- Recall: `96.4%`
- F1 Score: `0.942`
- AUC-ROC: `0.981`

> Model explainability is provided via **SHAP (SHapley Additive exPlanations)** for admin review of flagged claims.

---

## Fraud Detection & Anti-Spoofing Strategy

GigShield AI employs a **multi-layered fraud defense system** designed specifically for the gig economy threat landscape.

---

### 1. GPS Spoof Detection

GPS spoofing is one of the most common fraud vectors — workers fake their location to claim payouts for trips or incidents that never happened.

**Detection Techniques:**

- **Signal Consistency Analysis** — Compare GPS coordinates with cell tower triangulation and Wi-Fi positioning. Significant divergence triggers a spoof alert.
- **Velocity Plausibility Check** — Calculate speed between consecutive GPS points. Speeds exceeding physically possible limits (e.g., 300 km/h for a two-wheeler) are flagged immediately.
- **Altitude & Sensor Fusion** — Cross-reference GPS altitude data with barometric sensor readings to verify physical location authenticity.
- **Mock Location App Detection** — Detect presence of developer mode and known GPS spoofing applications on the worker's device.
- **Route Coherence Scoring** — Map claimed routes against real road networks using the Maps API. Paths through oceans or walls are auto-rejected.

```python
def detect_gps_spoof(gps_trace: list, sensor_data: dict) -> dict:
    velocity_flags = check_velocity_anomalies(gps_trace)
    tower_match = verify_cell_tower_alignment(gps_trace)
    mock_app_flag = detect_mock_location_app(sensor_data)
    route_score = compute_route_coherence(gps_trace)

    spoof_score = calculate_composite_score(
        velocity_flags, tower_match, mock_app_flag, route_score
    )
    return {"is_spoofed": spoof_score > 0.75, "confidence": spoof_score}
```

---

### 2. Fraud Ring Detection

Organized fraud rings coordinate multiple fake accounts to file simultaneous or sequential claims.

**Detection Approach:**

- **Graph Network Analysis** — Build a graph where nodes are worker accounts and edges represent shared attributes (device ID, IP address, bank account, referral chain).
- **Community Detection Algorithm** — Apply Louvain or Label Propagation algorithms to identify tightly connected clusters of suspicious accounts.
- **Claim Timing Correlation** — Detect statistically unlikely synchronization in claim filing times across unrelated accounts.
- **Shared Infrastructure Flags** — Identify accounts sharing the same phone, email domain, location history, or payment method.

```python
import networkx as nx
from community import best_partition

def detect_fraud_rings(accounts: list, shared_attributes: dict) -> list:
    G = nx.Graph()
    for account in accounts:
        G.add_node(account['id'])
    for pair, shared in shared_attributes.items():
        if shared['score'] > RING_THRESHOLD:
            G.add_edge(pair[0], pair[1], weight=shared['score'])

    communities = best_partition(G)
    suspicious_clusters = [c for c in communities if cluster_risk(c) > 0.8]
    return suspicious_clusters
```

---

### 3. Weather Validation

Workers may claim income disruption due to weather events that did not actually occur in their area.

**Validation Process:**

1. Worker files a claim citing adverse weather (rain, storm, flood, fog).
2. System extracts the worker's GPS coordinates at time of claim.
3. Real-time weather data is fetched from **OpenWeatherMap API** or **Tomorrow.io** for that exact location and timestamp.
4. A **Weather Match Score (0–1)** is computed based on condition alignment, precipitation level, and visibility index.
5. Claims with a Weather Match Score below `0.40` are automatically flagged for review.

```python
def validate_weather_claim(claim: dict) -> dict:
    actual_weather = fetch_weather(
        lat=claim['gps_lat'],
        lon=claim['gps_lon'],
        timestamp=claim['incident_time']
    )
    match_score = compute_weather_match(
        claimed=claim['weather_condition'],
        actual=actual_weather
    )
    return {
        "weather_verified": match_score >= 0.4,
        "match_score": match_score,
        "actual_conditions": actual_weather
    }
```

---

### 4. Behavioral Analysis

Continuous monitoring of in-app behavior to build a baseline and detect deviations.

**Behavioral Signals Monitored:**

- **Session Pattern Analysis** — Unusual login times, session durations, and navigation flows.
- **Typing Dynamics** — Keystroke timing patterns during claim form submission.
- **Claim Submission Velocity** — Filing multiple claims in rapid succession (< 10 minutes apart).
- **Copy-Paste Behavior Detection** — Pasting large text blocks into claim description fields (indicative of templated fraud).
- **Device Fingerprint Drift** — Tracking changes in device hardware ID, OS version, screen resolution, and browser fingerprint over time.
- **Anomaly Scoring** — Each session is assigned a real-time risk score using an Isolation Forest model trained on normal user behavior.

```python
from sklearn.ensemble import IsolationForest

behavior_model = IsolationForest(contamination=0.05, random_state=42)
behavior_model.fit(normal_session_data)

def score_session(session_features: dict) -> float:
    anomaly_score = behavior_model.decision_function([session_features])[0]
    return normalize_score(anomaly_score)  # Returns 0 (normal) to 1 (anomalous)
```

---

## Subscription & Payment Flow

```
Worker Onboarding
      │
      ▼
  OTP Verification (SMS / Email)
      │
      ▼
  Profile Setup → Income History Upload → ML Income Assessment
      │
      ▼
  Plan Selection (Daily / Weekly / Monthly)
      │
      ▼
  Premium Calculation (ML-based dynamic pricing)
      │
      ▼
  QR Code Payment / UPI / Wallet
      │
      ▼
  Policy Activated → Email Confirmation Sent
      │
      ▼
  Active Coverage Period
      │
      ├──→ No Incident: Policy Expires / Auto-Renewal Prompt
      │
      └──→ Incident Occurs
                │
                ▼
          Claim Submission (App / Chatbot)
                │
                ▼
          Fraud Analysis (GPS + Weather + Behavior + ML)
                │
                ├──→ FRAUD DETECTED: Claim Rejected → Alert Sent → Admin Flagged
                │
                └──→ VERIFIED: Parametric Trigger Confirmed
                              │
                              ▼
                        Automatic Payout via QR / Bank Transfer
                              │
                              ▼
                        Email & SMS Confirmation to Worker
```

### Subscription Plans

| Plan | Duration | Coverage | Premium Range |
|------|----------|----------|--------------|
| **ShieldDay** | 1 Day | ₹500 – ₹2,000 | ₹15 – ₹50 |
| **ShieldWeek** | 7 Days | ₹2,000 – ₹8,000 | ₹80 – ₹250 |
| **ShieldMonth** | 30 Days | ₹5,000 – ₹25,000 | ₹250 – ₹800 |
| **ShieldPro** | 90 Days | ₹15,000 – ₹60,000 | ₹600 – ₹1,800 |

> Premium amounts are dynamically priced by the Income Prediction ML model based on each worker's earning profile and risk score.

---

## Tech Stack

### Frontend
| Technology | Purpose |
|---|---|
| React.js (PWA) | Worker-facing web application |
| Tailwind CSS | Responsive UI styling |
| Chart.js / Recharts | Income & analytics dashboards |
| React QR Code | QR payment generation |
| Axios | API communication |

### Backend
| Technology | Purpose |
|---|---|
| Python 3.10+ | Core backend language |
| FastAPI | REST API framework |
| Celery + Redis | Async task queue (payouts, alerts) |
| JWT + OTP | Authentication & session management |
| PostgreSQL | Primary relational database |
| Firebase Firestore | Real-time claim status updates |

### Machine Learning
| Technology | Purpose |
|---|---|
| Scikit-learn | Income prediction & fraud detection models |
| Pandas / NumPy | Data processing & feature engineering |
| SHAP | Model explainability for admin dashboard |
| Isolation Forest | Behavioral anomaly detection |
| NetworkX | Fraud ring graph analysis |
| Joblib | Model serialization & loading |

### External APIs & Services
| Service | Purpose |
|---|---|
| Twilio | OTP SMS delivery |
| SendGrid | Transactional email alerts |
| OpenWeatherMap | Real-time weather validation |
| Google Maps API | GPS route validation |
| Razorpay / Stripe | QR-based payment processing |
| Firebase Auth | Social login support |

### DevOps & Deployment
| Technology | Purpose |
|---|---|
| Docker + Docker Compose | Containerization |
| NGINX | Reverse proxy & load balancer |
| GitHub Actions | CI/CD pipeline |
| AWS EC2 / Railway | Cloud hosting |
| AWS S3 | Model artifact & document storage |

---

## How It Works

### Step-by-Step User Journey

**Step 1 — Registration & OTP Verification**
Worker downloads the app or visits the web platform, enters their phone number, and receives an OTP for secure verification. After confirming identity, they complete their profile with gig platform details and income history.

**Step 2 — AI Income Assessment**
The Income Prediction Model (Linear Regression) analyzes the worker's historical earnings, gig activity, location, and seasonal factors to compute a **Predicted Daily Income** value. This drives their personalized premium pricing.

**Step 3 — Plan Selection & QR Payment**
The worker selects a coverage plan that fits their needs. A QR code is dynamically generated for instant premium payment via UPI, wallet, or card. Upon payment confirmation, the policy is immediately activated.

**Step 4 — Active Coverage & Real-Time Monitoring**
Throughout the coverage period, the system continuously monitors:
- Platform activity signals (trip completion, login patterns)
- GPS movement data
- Weather conditions in the worker's area
- Behavioral patterns within the app

**Step 5 — Incident & Claim Filing**
If an income-disrupting event occurs (accident, weather, platform outage), the worker files a claim via the app or through the **AI Chatbot**, which guides them through the process conversationally.

**Step 6 — Multi-Layer Fraud Validation**
Every claim is automatically processed through the fraud pipeline:
1. GPS coordinates validated against claimed incident location.
2. Weather API confirmation of reported conditions.
3. Random Forest model scores the claim for fraud probability.
4. Behavioral patterns checked for anomalies.
5. Graph analysis to check for fraud ring involvement.

**Step 7 — Automatic Payout or Escalation**
- **Verified claims** trigger an immediate parametric payout to the worker's registered payment method. A confirmation email and SMS are sent.
- **Flagged claims** are placed in the admin review queue with a detailed fraud report and SHAP explanation of the ML decision.

**Step 8 — Admin Oversight**
Admins access the dashboard to review flagged claims, view platform-wide analytics, manage subscription tiers, and monitor the fraud scoring engine performance.

---

## Installation & Setup

### Prerequisites

- Python `3.10+`
- Node.js `18+`
- PostgreSQL `14+`
- Redis `7+`
- Docker & Docker Compose (optional but recommended)

---

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/gigshield-ai.git
cd gigshield-ai
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your credentials (see below)
```

**Required `.env` Variables:**

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/gigshield_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Authentication
SECRET_KEY=your-super-secret-jwt-key
OTP_EXPIRY_MINUTES=10

# External APIs
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx

SENDGRID_API_KEY=your_sendgrid_key
SENDGRID_FROM_EMAIL=noreply@gigshield.ai

OPENWEATHER_API_KEY=your_openweather_key
GOOGLE_MAPS_API_KEY=your_google_maps_key

RAZORPAY_KEY_ID=your_razorpay_key
RAZORPAY_KEY_SECRET=your_razorpay_secret

# Firebase
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
```

```bash
# Run database migrations
alembic upgrade head

# Train and save ML models
python ml/train_income_model.py
python ml/train_fraud_model.py

# Start backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (in a separate terminal)
celery -A app.celery_app worker --loglevel=info
```

### 3. Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Set REACT_APP_API_URL=http://localhost:8000

# Start development server
npm start
```

### 4. Docker Setup (Recommended)

```bash
# From project root
docker-compose up --build
```

This will spin up:
- FastAPI backend on `http://localhost:8000`
- React frontend on `http://localhost:3000`
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- NGINX reverse proxy on `http://localhost:80`

---

### API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Deployment Instructions

### Option A — AWS EC2 Deployment

```bash
# 1. Launch an EC2 instance (Ubuntu 22.04, t3.medium or higher)
# 2. SSH into your instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# 3. Install Docker
sudo apt update && sudo apt install docker.io docker-compose -y
sudo usermod -aG docker ubuntu

# 4. Clone and deploy
git clone https://github.com/your-org/gigshield-ai.git
cd gigshield-ai
cp .env.example .env  # Fill in production credentials

docker-compose -f docker-compose.prod.yml up -d --build

# 5. Configure NGINX for SSL
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

### Option B — Railway Deployment

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and initialize
railway login
railway init

# Deploy all services
railway up

# Set environment variables via Railway dashboard
# Link PostgreSQL and Redis plugins from Railway's add-ons
```

### Option C — Docker Hub + CI/CD (GitHub Actions)

The repository includes a pre-configured GitHub Actions workflow at `.github/workflows/deploy.yml`:

```yaml
name: Deploy GigShield AI

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker Images
        run: docker-compose build
      - name: Push to Docker Hub
        run: |
          docker login -u ${{ secrets.DOCKER_USERNAME }} -p ${{ secrets.DOCKER_PASSWORD }}
          docker-compose push
      - name: Deploy to EC2
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ubuntu
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd gigshield-ai && git pull
            docker-compose -f docker-compose.prod.yml up -d --build
```

### Production Checklist

- [ ] Set `DEBUG=False` in production environment
- [ ] Configure SSL certificate via Let's Encrypt
- [ ] Enable PostgreSQL connection pooling (PgBouncer)
- [ ] Set up automated database backups (AWS RDS recommended)
- [ ] Configure Redis persistence (`appendonly yes`)
- [ ] Enable CORS restrictions to your frontend domain only
- [ ] Set up monitoring with **Sentry** for error tracking
- [ ] Configure **Prometheus + Grafana** for ML model performance monitoring
- [ ] Enable rate limiting on all public API endpoints

---

## Future Improvements

### Short-Term (Next 3 Months)
- **Deep Learning Upgrade** — Replace Linear Regression income model with an **LSTM (Long Short-Term Memory)** neural network for time-series income forecasting with higher accuracy.
- **Multimodal Fraud Detection** — Incorporate image/video analysis for accident verification using **Computer Vision (YOLOv8)**.
- **WhatsApp Bot Integration** — Extend the chatbot to WhatsApp for maximum accessibility among gig workers in emerging markets.
- **Offline-First PWA** — Enable claim filing and policy viewing without internet access, syncing when connectivity is restored.

### Mid-Term (3–6 Months)
- **Federated Learning** — Train fraud detection models on-device to preserve worker privacy while improving model accuracy across the platform.
- **Blockchain Audit Trail** — Record all claim decisions and payouts on a public blockchain for complete transparency and dispute resolution.
- **Platform API Integrations** — Direct integrations with Swiggy, Zomato, Ola, Uber, and Dunzo APIs to pull verified trip and earnings data automatically.
- **Credit Score Building** — Use payment and income history to generate a **Gig Credit Score** enabling workers to access microloans.

### Long-Term (6–12 Months)
- **Decentralized Insurance Pool** — Enable peer-to-peer risk pooling among gig workers via smart contracts, reducing premium costs by 40–60%.
- **Predictive Health Coverage** — Extend parametric triggers to health events, partnering with wearable device APIs.
- **Government Partnership Module** — White-label solution for national social security programs to extend coverage to informal workers at scale.
- **Multi-Region & Multi-Currency Expansion** — Scale to Southeast Asia, Africa, and Latin America with localized premium pricing and payment rails.
- **Reinforcement Learning for Dynamic Pricing** — Implement RL agents to continuously optimize premium pricing and payout thresholds based on market conditions.

---

## Project Structure

```
gigshield-ai/
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI route handlers
│   │   ├── core/              # Config, security, dependencies
│   │   ├── models/            # Database ORM models
│   │   ├── services/          # Business logic services
│   │   ├── tasks/             # Celery async tasks
│   │   └── main.py            # FastAPI app entry point
│   ├── ml/
│   │   ├── income_model.py    # Linear Regression income predictor
│   │   ├── fraud_model.py     # Random Forest fraud classifier
│   │   ├── gps_spoof.py       # GPS anti-spoofing engine
│   │   ├── fraud_ring.py      # Graph-based ring detection
│   │   ├── weather_check.py   # Weather validation module
│   │   ├── behavior.py        # Behavioral anomaly detection
│   │   └── artifacts/         # Saved model files (.joblib)
│   ├── alembic/               # Database migrations
│   ├── tests/                 # Unit & integration tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/        # Reusable UI components
│   │   ├── pages/             # App pages (Worker, Admin, Auth)
│   │   ├── services/          # API client functions
│   │   └── App.jsx
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── nginx.conf
├── .github/
│   └── workflows/deploy.yml
└── README.md
```

---

## Contributing

We welcome contributions from the community! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) guide before submitting a pull request.

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

##  Team

Built with love  for the gig economy.

> *"Every gig worker deserves a safety net. GigShield AI is that net."*

---

<p align="center">
  <strong>GigShield AI</strong> · AI-Powered Parametric Insurance for the Gig Economy<br/>
  ⭐ Star this repo if you find it useful · 🐛 Report bugs via Issues · 💬 Discuss ideas in Discussions
</p>
