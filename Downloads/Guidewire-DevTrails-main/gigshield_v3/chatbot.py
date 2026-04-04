"""GigShield AI — Rule-Based Chatbot"""

import re

INTENTS = [
    (["premium","how much","cost","fees","price","subscription cost"],
     "💰 *Premium:* ₹49/week (Swiggy) · ₹59/week (Zomato) · ₹39/week (Others).\nCoverage = 20× weekly premium. Minimum 7-day subscription."),
    (["how to claim","file a claim","claim process","apply claim","submit claim"],
     "📋 *Claim Process:*\n1. Subscription must be active.\n2. Weather disruption detected in your city.\n3. Open dashboard → tap *Trigger Claim*.\n4. ML fraud check runs in real-time. Approved claims pay out within 24 hrs."),
    (["fraud","fraud detection","anti-fraud","gps spoof","fake claim"],
     "🛡️ *Fraud Detection:*\nWe combine RandomForest ML (6 features) + 7 hard rules.\nGPS variance, login frequency, device fingerprinting, weather matching and claim frequency are all monitored.\nFraud rings (multiple accounts / same device) are auto-rejected."),
    (["subscription","validity","7 days","renew","expiry","expire"],
     "📅 *Subscription:* 7-day minimum. You get an alert when 2 days remain.\nRenew anytime from your dashboard via UPI QR scan."),
    (["payout","how much will i get","claim amount","payout calculated"],
     "💸 *Payout:* Our LinearRegression ML estimates income loss from disrupted hours (≈₹90/hr).\nPayout is capped at your weekly coverage amount."),
    (["weather","rain","storm","weather detected","weather check"],
     "🌧️ *Weather:* We pull real-time data from OpenWeatherMap for your city.\nDisruptions (rain, cyclone, fog, extreme heat) trigger eligibility. Weather mismatches are flagged as fraud."),
    (["register","sign up","how to join","create account"],
     "✅ *Register:*\n1. Select Worker on home screen.\n2. Enter name, city, platform, Worker ID, phone.\n3. Verify OTP (real SMS via Twilio).\n4. Scan UPI QR → Pay → Done!"),
    (["gps","location","why location","gps check"],
     "📍 *GPS:* We analyse GPS variance across claim sessions.\nLegit workers show consistent movement patterns.\nExtreme variance or zero movement triggers our anti-spoofing rules."),
    (["device","device id","same device","multiple accounts"],
     "📱 *Device Fraud:* Each device ID is registered to one worker.\nMultiple accounts sharing a device are flagged as a fraud ring and auto-rejected."),
    (["otp","one time password","sms","phone verify"],
     "📱 *OTP:* We send a real 6-digit OTP via Twilio SMS.\nIn dev mode it prints to the console. OTP is valid for one use only."),
    (["hello","hi","hey","namaste","good morning","good evening"],
     "👋 Hello! I'm *GigShield Support Bot*. Ask me about premium, claims, fraud, subscriptions, or OTP!"),
    (["thank","thanks","thank you","great","awesome","perfect"],
     "😊 Happy to help! Your income is protected. Stay safe on the roads. 🛡️"),
    (["contact","support","email","help"],
     "📞 *Support:* support@gigshield.ai · WhatsApp: +91-9876543210 · Mon–Sat 9AM–6PM IST"),
    (["help","what can you do","menu","options"],
     "🤖 Ask me about:\n• Premium & pricing\n• Claim process\n• Fraud detection\n• GPS & device safety\n• OTP & registration\n• Weather triggers\n• Subscription"),
]
FALLBACK = "🤔 I didn't catch that. Try: *premium · claim · fraud · subscription · weather · otp*"

def get_response(msg: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", "", msg.lower().strip())
    if not n: return FALLBACK
    for patterns, resp in INTENTS:
        if any(p in n for p in patterns):
            return resp
    return FALLBACK
