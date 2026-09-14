import json
import os
import urllib.error
import urllib.request

import boto3

REGION = "ap-southeast-1"
UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"

_secrets = boto3.client("secretsmanager", region_name=REGION)
_resend_cache = None


def _get_resend():
    global _resend_cache
    if _resend_cache is None:
        raw = _secrets.get_secret_value(SecretId="flight/resend")["SecretString"]
        _resend_cache = json.loads(raw)
    return _resend_cache


def _plan_from(route):
    if route == "TPE-TYO":
        return "台北", "東京"
    if route == "TPE-SEL":
        return "台北", "首爾"
    o, d = route.split("-")
    return o, d


def _send_resend(resend_cfg, to_email, subj, html, text):
    body = {
        "from": resend_cfg["from"],
        "to": to_email,
        "subject": subj,
        "html": html,
        "text": text,
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {resend_cfg['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print("RESEND_OK", r.status, r.read().decode())
            return True
    except urllib.error.HTTPError as e:
        print("RESEND_ERR", e.code, e.read().decode())
        return False


def _welcome_email(plan_from, plan_to):
    subject = f"🎉 歡迎訂閱 {plan_from} → {plan_to} 機票降價通知"
    html = f"""
    <div>
      <h2>訂閱成功！</h2>
      <p>{plan_from} → {plan_to} 的機票降價通知已經啟用，降到你的目標價就會寄信給你。</p>
      <p style="color:#888;font-size:12px;">Flight Price Notifier</p>
    </div>
    """.strip()
    text = f"訂閱成功！{plan_from} -> {plan_to} 的機票降價通知已經啟用。"
    return subject, html, text


def _cancel_email(plan_from, plan_to):
    subject = f"已取消訂閱 {plan_from} → {plan_to}"
    html = f"""
    <div>
      <h2>訂閱已取消</h2>
      <p>{plan_from} → {plan_to} 的機票降價通知已取消續扣款，在目前計費週期結束前你仍會收到通知。</p>
      <p style="color:#888;font-size:12px;">Flight Price Notifier</p>
    </div>
    """.strip()
    text = f"{plan_from} -> {plan_to} 的訂閱已取消續扣款，週期結束前仍會通知。"
    return subject, html, text


def _process(msg):
    event_type = msg.get("event_type")
    email = msg["email"]
    route = msg["route"]
    plan_from, plan_to = _plan_from(route)

    if event_type == "welcome":
        subject, html, text = _welcome_email(plan_from, plan_to)
    elif event_type == "cancel":
        subject, html, text = _cancel_email(plan_from, plan_to)
    else:
        print("unknown event_type, skipping", event_type)
        return

    resend_cfg = _get_resend()
    sent = _send_resend(resend_cfg, email, subject, html, text)
    print("sent" if sent else "dropped", event_type, email, route)


def handler(event, context):
    for record in event.get("Records", []):
        msg = json.loads(record["body"])
        _process(msg)
    return {"ok": True}
