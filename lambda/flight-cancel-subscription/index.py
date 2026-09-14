import calendar
import datetime
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import boto3

REGION = "ap-southeast-1"
STATUS_QUEUE_URL = os.environ["STATUS_QUEUE_URL"]
UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"

ddb = boto3.resource("dynamodb", region_name=REGION).Table("subscriptions")
_secrets = boto3.client("secretsmanager", region_name=REGION)
_sqs = boto3.client("sqs", region_name=REGION)

_ecpay_cache = None


def _get_ecpay():
    global _ecpay_cache
    if _ecpay_cache is None:
        raw = _secrets.get_secret_value(SecretId="flight/ecpay")["SecretString"]
        _ecpay_cache = json.loads(raw)
    return _ecpay_cache


def ecpay_url_encode(s: str) -> str:
    e = urllib.parse.quote_plus(str(s)).replace("~", "%7E")
    e = e.lower()
    for o, n in (
        ("%2d", "-"), ("%5f", "_"), ("%2e", "."), ("%21", "!"),
        ("%2a", "*"), ("%28", "("), ("%29", ")"),
    ):
        e = e.replace(o, n)
    return e


def gen_cmv(params: dict, hash_key: str, hash_iv: str) -> str:
    items = {k: v for k, v in params.items() if k != "CheckMacValue"}
    body = "&".join(f"{k}={items[k]}" for k in sorted(items, key=str.lower))
    raw = f"HashKey={hash_key}&{body}&HashIV={hash_iv}"
    return hashlib.sha256(ecpay_url_encode(raw).encode()).hexdigest().upper()


def add_one_month(dt):
    y, m = dt.year, dt.month + 1
    if m > 12:
        y, m = y + 1, 1
    last_day = calendar.monthrange(y, m)[1]
    return dt.replace(year=y, month=m, day=min(dt.day, last_day))


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def _call_ecpay_cancel(cfg, merchant_trade_no):
    params = {
        "MerchantID": cfg["merchant_id"],
        "MerchantTradeNo": merchant_trade_no,
        "Action": "Cancel",
        "TimeStamp": str(int(time.time())),
    }
    params["CheckMacValue"] = gen_cmv(params, cfg["hash_key"], cfg["hash_iv"])
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        "https://payment-stage.ecpay.com.tw/Cashier/CreditCardPeriodAction",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode()
            print("ECPay cancel response:", body)
            return body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print("ECPay cancel HTTPError:", e.code, body)
        return body


def handler(event, context):
    try:
        raw = event.get("body", event)
        body = json.loads(raw) if isinstance(raw, str) else raw
        email = (body.get("email") or "").strip().lower()
        route = body.get("route")

        if not email or not route:
            return _response(400, {"error": "email and route required"})

        item = ddb.get_item(Key={"email": email, "route": route}).get("Item")
        if not item:
            return _response(404, {"error": "subscription not found"})

        if item.get("subscription_status") not in ("active", "cancelled"):
            return _response(400, {"error": "subscription is not active"})

        merchant_trade_no = item.get("merchant_trade_no")
        cfg = _get_ecpay()
        if merchant_trade_no:
            ecpay_result = _call_ecpay_cancel(cfg, merchant_trade_no)
            # Stage cancel of a synthetic/never-truly-scheduled order returns
            # 90100150 不存在的訂單編號 — expected; log it and still cancel locally.
            print("cancel call result:", ecpay_result)

        now = datetime.datetime.now(datetime.timezone.utc)
        current_period_end = item.get("current_period_end")
        if not current_period_end:
            # Migration fallback: a row with no period-tracking yet (e.g. a legacy
            # M1 row) gets a grace window instead of expiring immediately.
            current_period_end = add_one_month(now).strftime("%Y-%m-%dT%H:%M:%SZ")

        ddb.update_item(
            Key={"email": email, "route": route},
            UpdateExpression=(
                "SET subscription_status = :cancelled, current_period_end = :end, "
                "updated_at = :now"
            ),
            ExpressionAttributeValues={
                ":cancelled": "cancelled",
                ":end": current_period_end,
                ":now": now.isoformat(),
            },
        )

        _sqs.send_message(
            QueueUrl=STATUS_QUEUE_URL,
            MessageBody=json.dumps({"event_type": "cancel", "email": email, "route": route}),
        )

        return _response(200, {"ok": True, "subscription_status": "cancelled", "current_period_end": current_period_end})
    except Exception as e:
        print("ERROR", repr(e))
        return _response(500, {"error": "internal error"})
