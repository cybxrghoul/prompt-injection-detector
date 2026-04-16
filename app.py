from flask import Flask, render_template, request, jsonify
import csv
import os
from datetime import datetime
import joblib
import re
import base64
import urllib.parse

app = Flask(__name__)

LOG_CSV = "data/detection_logs.csv"

ATTACK_PATTERNS = {
    "Prompt Injection": [
        r"ignore (all|previous) instructions",
        r"disregard (above|previous)",
        r"you are now"
    ],
    "Data Exfiltration": [
        r"reveal (system|hidden|secret)",
        r"show (config|password|token)",
        r"print .*env"
    ],
    "Jailbreak Attempt": [
        r"act as .* without restrictions",
        r"bypass .* safety",
        r"simulate .* unrestricted"
    ],
    "Role Hijacking": [
        r"you are chatgpt",
        r"you are developer",
        r"system override"
    ]
}

def detect_attack_type(prompt):
    detected = []
    for attack, patterns in ATTACK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, prompt.lower()):
                detected.append(attack)
                break
    return detected

def detect_and_decode(prompt):
    decoded_versions = []
    encoding_detected = []

    try:
        if len(prompt) % 4 == 0:
            decoded = base64.b64decode(prompt).decode('utf-8')
            if decoded.isprintable():
                decoded_versions.append(decoded)
                encoding_detected.append("Base64")
    except:
        pass

    if "%" in prompt:
        try:
            decoded = urllib.parse.unquote(prompt)
            if decoded != prompt:
                decoded_versions.append(decoded)
                encoding_detected.append("URL Encoding")
        except:
            pass

    return decoded_versions, encoding_detected

def calculate_risk_score(prompt, ml_prediction, detected_attacks):
    score = 0

    if ml_prediction == 1:
        score += 40

    score += len(detected_attacks) * 20

    if len(prompt) > 200:
        score += 10

    suspicious_words = ["ignore", "bypass", "reveal", "override"]
    score += sum(word in prompt.lower() for word in suspicious_words) * 5

    if any(c in prompt for c in ["=", "%", "0x"]):
        score += 15

    return min(score, 100)

def mitigate_prompt(prompt, detected_attacks):
    if not detected_attacks:
        return prompt, "No mitigation needed", False

    return "[BLOCKED: Potential Prompt Injection Detected]", f"Blocked due to: {', '.join(detected_attacks)}", True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/logs')
def logs_page():
    return render_template('logs.html')

@app.route('/analyze_prompt', methods=['POST'])
def analyze_prompt():
    data = request.json
    prompt = data.get('prompt', '')

    # Load ML model
    vectorizer = joblib.load("ml/vectorizer.pkl")
    clf = joblib.load("ml/classifier.pkl")

    X = vectorizer.transform([prompt])
    ml_prob = float(clf.predict_proba(X)[0, 1])
    ml_label = int(clf.predict(X)[0])

    decoded_versions, encodings = detect_and_decode(prompt)

    detected_attacks = detect_attack_type(prompt)

    for decoded in decoded_versions:
        decoded_attacks = detect_attack_type(decoded)
        if decoded_attacks:
            detected_attacks.extend(decoded_attacks)
            detected_attacks.append("Obfuscated Attack")

    detected_attacks = list(set(detected_attacks))

    risk_score = calculate_risk_score(prompt, ml_label, detected_attacks)

    safe_prompt, mitigation_reason, blocked = mitigate_prompt(prompt, detected_attacks)

    if risk_score >= 75:
        severity = "CRITICAL"
    elif risk_score >= 50:
        severity = "HIGH"
    elif risk_score >= 25:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return jsonify({
        "original_prompt": prompt,
        "safe_prompt": safe_prompt,
        "ml_risk_score": round(ml_prob * 100, 2),
        "ml_label": ml_label,
        "detected_attacks": detected_attacks,
        "encoding_detected": encodings,
        "decoded_payloads": decoded_versions,
        "risk_score": risk_score,
        "severity": severity,
        "blocked": blocked,
        "mitigation_reason": mitigation_reason
    })

@app.route('/log_detection', methods=['POST'])
def log_detection():
    data = request.json

    if not os.path.exists('data'):
        os.makedirs('data')

    is_new_file = not os.path.exists(LOG_CSV)

    try:
        with open(LOG_CSV, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)

            if is_new_file:
                writer.writerow(['timestamp', 'prompt', 'overallRisk', 'blocked', 'patterns', 'topFinding'])

            writer.writerow([
                datetime.now().isoformat(),
                data.get('prompt', '')[:200],
                data.get('overallRisk', 0),
                data.get('blocked', False),
                ', '.join(data.get('patterns', [])),
                data.get('topFinding', '')
            ])

        return jsonify({'status': 'ok'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/detection_logs')
def api_detection_logs():
    data = []
    try:
        with open(LOG_CSV, newline='', encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
    except Exception as e:
        return jsonify({"error": f"No log file found or read error: {e}", "logs": []})

    return jsonify({"logs": data})

@app.route('/api/malicious_prompts')
def api_malicious_prompts():
    data = []
    try:
        with open(LOG_CSV, newline='', encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                is_mal = (
                    (row.get('blocked', '').lower() == 'true') or
                    (row.get('overallRisk', '0').isdigit() and int(row.get('overallRisk', '0')) >= 40)
                )
                if is_mal:
                    data.append(row)
    except Exception as e:
        return jsonify({"error": f"No log file found or read error: {e}", "malicious_prompts": []})

    return jsonify({"malicious_prompts": data})


if __name__ == '__main__':
    app.run(debug=True)
