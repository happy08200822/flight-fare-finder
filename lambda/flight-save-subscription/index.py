import os
import boto3
import json
import time
import uuid
import datetime
import hashlib
import urllib.parse
from decimal import Decimal, InvalidOperation

PLANS = {
    "tokyo": {"origin": "TPE", "destination": "TYO", "label": "台北 ✈ 東京"},
    "seoul": {"origin": "TPE", "destination": "SEL", "label": "台北 ✈ 首爾"},
}

REGION = "ap-southeast-1"
API_BASE = os.environ["API_BASE"]
SITE_URL = os.environ["SITE_URL"]
CASHIER_URL = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"

ddb = boto3.resource("dynamodb", region_name=REGION).Table("subscriptions")
_secrets = boto3.client("secretsmanager", region_name=REGION)

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


def _json_response(status, payload):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def _html_response(html):
    return {
        "statusCode": 200,
        "headers": {"content-type": "text/html; charset=utf-8"},
        "body": html,
    }


def _build_checkout_form(email, route, plan, amount, merchant_trade_no, ecpay_cfg):
    now_tw = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    params = {
        "MerchantID": ecpay_cfg["merchant_id"],
        "MerchantTradeNo": merchant_trade_no,
        "MerchantTradeDate": now_tw.strftime("%Y/%m/%d %H:%M:%S"),
        "PaymentType": "aio",
        "TotalAmount": str(amount),
        "TradeDesc": "FlightPriceNotifierSubscription",
        "ItemName": f"{plan['label']} 機票通知訂閱",
        "ReturnURL": f"{API_BASE}/ecpay-return",
        "ChoosePayment": "Credit",
        "EncryptType": "1",
        "PeriodAmount": str(amount),
        "PeriodType": "M",
        "Frequency": "1",
        "ExecTimes": "999",
        "PeriodReturnURL": f"{API_BASE}/ecpay-period",
        "OrderResultURL": f"{API_BASE}/ecpay-result",
        "CustomField1": email,
        "CustomField2": route,
    }
    params["CheckMacValue"] = gen_cmv(params, ecpay_cfg["hash_key"], ecpay_cfg["hash_iv"])

    inputs = "\n".join(
        f'<input type="hidden" name="{k}" value="{v}">' for k, v in params.items()
    )
    return f"""<!doctype html>
<html><body>
<form id="ecpay-form" method="post" action="{CASHIER_URL}">
{inputs}
</form>
<script>document.getElementById('ecpay-form').submit();</script>
</body></html>"""


def handler(event, context):
    try:
        raw = event.get("body", event)
        body = json.loads(raw) if isinstance(raw, str) else raw

        email = (body.get("email") or "").strip().lower()
        plan_name = body.get("plan_name")
        target_price = body.get("target_price")

        if not email or "@" not in email:
            return _json_response(400, {"error": "invalid email"})
        if plan_name not in PLANS:
            return _json_response(400, {"error": "invalid plan_name"})
        try:
            target_price_dec = Decimal(str(target_price))
        except (InvalidOperation, TypeError):
            return _json_response(400, {"error": "invalid target_price"})
        if target_price_dec <= 0:
            return _json_response(400, {"error": "target_price must be positive"})

        plan = PLANS[plan_name]
        origin, destination = plan["origin"], plan["destination"]
        route = f"{origin}-{destination}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        existing = ddb.get_item(Key={"email": email, "route": route}).get("Item")

        # Paid (active) or in-grace (cancelled) subscribers just update target price in place —
        # no re-payment, and we must never knock a paid user back to pending_payment.
        if existing and existing.get("subscription_status") in ("active", "cancelled"):
            ddb.update_item(
                Key={"email": email, "route": route},
                UpdateExpression="SET target_price = :t, updated_at = :u",
                ExpressionAttributeValues={":t": target_price_dec, ":u": now},
            )
            return _json_response(
                200,
                {
                    "ok": True,
                    "route": route,
                    "subscription_status": existing["subscription_status"],
                },
            )

        merchant_trade_no = f"FPN{int(time.time())}{uuid.uuid4().hex[:6]}"[:20]
        created_at = existing["created_at"] if existing else now

        ddb.put_item(
            Item={
                "email": email,
                "route": route,
                "plan_name": plan_name,
                "origin": origin,
                "destination": destination,
                "target_price": target_price_dec,
                "currency": "TWD",
                "subscription_status": "pending_payment",
                "merchant_trade_no": merchant_trade_no,
                "created_at": created_at,
                "updated_at": now,
            }
        )

        ecpay_cfg = _get_ecpay()
        html = _build_checkout_form(
            email, route, plan, ecpay_cfg["amount"], merchant_trade_no, ecpay_cfg
        )
        return _html_response(html)
    except Exception as e:
        print("ERROR", repr(e))
        return _json_response(500, {"error": "internal error"})
