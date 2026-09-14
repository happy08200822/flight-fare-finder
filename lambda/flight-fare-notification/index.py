import os
import json
import datetime
import urllib.request
import urllib.error

import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal

REGION = "ap-southeast-1"
UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"

NOTIFY_FLOOR_HOURS = float(os.environ.get("NOTIFY_FLOOR_HOURS", "24"))
REALERT_PCT = float(os.environ.get("REALERT_PCT", "20"))
REALERT_ABS_TWD = float(os.environ.get("REALERT_ABS_TWD", "2000"))

_secrets = boto3.client("secretsmanager", region_name=REGION)
_history = boto3.resource("dynamodb", region_name=REGION).Table("notification_history")

_resend_cache = None

PLAN_LABELS = {
    "tokyo": ("台北", "東京"),
    "seoul": ("台北", "首爾"),
}


def _get_resend():
    global _resend_cache
    if _resend_cache is None:
        raw = _secrets.get_secret_value(SecretId="flight/resend")["SecretString"]
        _resend_cache = json.loads(raw)
    return _resend_cache


def _should_send(email, route, new_price):
    pk = f"{email}#{route}"
    result = _history.query(
        KeyConditionExpression=Key("pk").eq(pk),
        ScanIndexForward=False,
        Limit=1,
    )
    items = result.get("Items", [])
    if not items:
        return True

    last = items[0]
    last_sent_at = datetime.datetime.fromisoformat(last["sent_at"])
    now = datetime.datetime.now(datetime.timezone.utc)
    hours_since = (now - last_sent_at).total_seconds() / 3600.0
    if hours_since >= NOTIFY_FLOOR_HOURS:
        return True

    last_price = float(last["price"])
    if new_price <= last_price * (1 - REALERT_PCT / 100.0):
        return True
    if (last_price - new_price) >= REALERT_ABS_TWD:
        return True

    return False


def _ddmm(iso_str):
    if not iso_str:
        return ""
    dt = datetime.datetime.fromisoformat(iso_str)
    return f"{dt.day:02d}{dt.month:02d}"


def booking_url(origin, destination, depart_date, return_date, marker=None):
    url = f"https://www.aviasales.com/search/{origin}{_ddmm(depart_date)}{destination}{_ddmm(return_date)}1"
    if marker:
        url += f"?marker={marker}"
    return url


def subject(plan_from, plan_to, price_twd):
    return f"✈️ {plan_from} → {plan_to} 降價通知！NT${price_twd:,} 已達標"


def render_html(plan_from, plan_to, price_twd, target_price, book_url, usd_price=None):
    usd_line = f"<p>約 US${usd_price:,}</p>" if usd_price is not None else ""
    return f"""
    <div>
      <h2>{plan_from} → {plan_to}：機票降價了！</h2>
      <p style="font-size:24px;font-weight:700;">NT${price_twd:,}</p>
      {usd_line}
      <p>你設定的目標價是 NT${target_price:,}，現在已經達標。</p>
      <p><a href="{book_url}" style="display:inline-block;padding:10px 20px;background:#e8664e;color:#fff;border-radius:8px;text-decoration:none;">立即訂購</a></p>
      <p style="color:#888;font-size:12px;">Flight Price Notifier</p>
    </div>
    """.strip()


def render_text(plan_from, plan_to, price_twd, target_price, book_url, usd_price=None):
    lines = [
        f"{plan_from} -> {plan_to}: NT${price_twd:,}",
    ]
    if usd_price is not None:
        lines.append(f"約 US${usd_price:,}")
    lines.append(f"你設定的目標價是 NT${target_price:,}，現在已經達標。")
    lines.append(f"立即訂購: {book_url}")
    return "\n".join(lines)


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
        err_body = e.read().decode()
        print("RESEND_ERR", e.code, err_body)
        if e.code in (403, 422):
            # permanent failure — log + drop, don't retry
            return False
        # transient (429 / 5xx) — re-raise so SQS redelivers
        raise


def _process(msg):
    email = msg["email"]
    route = msg["route"]
    plan_name = msg.get("plan_name")
    target_price = msg["target_price"]
    cheapest = msg["cheapest"]
    cheapest_usd = msg.get("cheapest_usd")
    price_twd = cheapest["price"]

    if not _should_send(email, route, price_twd):
        print("skipped (deduped)", email, route, price_twd)
        return

    plan_from, plan_to = PLAN_LABELS.get(plan_name, tuple(route.split("-")))
    origin, destination = route.split("-")
    book_url = booking_url(origin, destination, cheapest.get("depart_date"), cheapest.get("return_date"))
    usd_price = cheapest_usd["price"] if cheapest_usd else None

    subj = subject(plan_from, plan_to, price_twd)
    html = render_html(plan_from, plan_to, price_twd, target_price, book_url, usd_price)
    text = render_text(plan_from, plan_to, price_twd, target_price, book_url, usd_price)

    resend_cfg = _get_resend()
    sent = _send_resend(resend_cfg, email, subj, html, text)

    if sent:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _history.put_item(
            Item={
                "pk": f"{email}#{route}",
                "sent_at": now,
                "email": email,
                "route": route,
                "price": Decimal(str(price_twd)),
                "currency": "TWD",
            }
        )
        print("sent + recorded", email, route, price_twd)
    else:
        print("dropped (permanent failure)", email, route)


def handler(event, context):
    for record in event.get("Records", []):
        msg = json.loads(record["body"])
        _process(msg)
    return {"ok": True}
