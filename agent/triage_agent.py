import os
import json
import logging
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

def query_groq(alert_context: str) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")

    prompt = f"""You are a senior DevOps engineer and SRE doing alert triage.

Analyze the following Prometheus alert and provide a structured triage report.

Format your response EXACTLY like this:

*Alert Triage Report*

*Alert:* [alert name]
*Severity:* [critical/warning/info]
*Summary:* [one sentence describing what happened]

*Probable Cause:*
[2-3 sentences explaining the most likely root cause]

*Immediate Actions:*
1. [First thing to check or do]
2. [Second thing to check or do]
3. [Third thing to check or do]

*Suggested Fix:*
[Concrete steps to resolve the issue]

*Verdict:* [CRITICAL - PAGE ON-CALL / WARNING - MONITOR CLOSELY / INFO - LOG AND IGNORE]

---
Alert details:
{alert_context}
"""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise ValueError(f"Groq error: {data['error']['message']}")

    if not data.get("choices") or len(data["choices"]) == 0:
        raise ValueError(f"Empty response from Groq: {json.dumps(data)}")

    return data["choices"][0]["message"]["content"]


def post_to_slack(message: str, alert_name: str, severity: str):
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not set — printing to console only")
        print(message)
        return

    color_map = {
        "critical": "#FF0000",
        "warning":  "#FFA500",
        "info":     "#36a64f"
    }
    color = color_map.get(severity.lower(), "#888888")

    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"AIOps Triage — {alert_name}",
                "text": message,
                "footer": f"AIOps Agent | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "mrkdwn_in": ["text"]
            }
        ]
    }

    response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
    response.raise_for_status()
    logger.info(f"Triage report posted to Slack for alert: {alert_name}")


@app.route('/webhook', methods=['POST'])
def handle_alert():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data received"}), 400

    logger.info(f"Alert received: {json.dumps(data, indent=2)}")

    alerts = data.get("alerts", [])

    if not alerts:
        return jsonify({"status": "no alerts to process"}), 200

    for alert in alerts:
        alert_name = alert.get("labels", {}).get("alertname", "Unknown")
        severity   = alert.get("labels", {}).get("severity", "info")
        status     = alert.get("status", "firing")
        instance   = alert.get("labels", {}).get("instance", "unknown")
        description = alert.get("annotations", {}).get("description", "No description")
        summary     = alert.get("annotations", {}).get("summary", "No summary")
        starts_at   = alert.get("startsAt", "unknown")

        alert_context = f"""
Alert Name: {alert_name}
Status: {status}
Severity: {severity}
Instance: {instance}
Summary: {summary}
Description: {description}
Started At: {starts_at}
All Labels: {json.dumps(alert.get('labels', {}), indent=2)}
"""

        logger.info(f"Processing alert: {alert_name} | severity: {severity}")

        try:
            triage_report = query_groq(alert_context)
            post_to_slack(triage_report, alert_name, severity)
            logger.info(f"Triage complete for: {alert_name}")

        except Exception as e:
            logger.error(f"Failed to triage alert {alert_name}: {str(e)}")
            error_msg = f"*AIOps Agent Error*\nFailed to triage alert `{alert_name}`\nError: {str(e)}"
            if SLACK_WEBHOOK_URL:
                requests.post(SLACK_WEBHOOK_URL, json={"text": error_msg}, timeout=10)

    return jsonify({"status": "processed", "alerts_count": len(alerts)}), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)