import base64
import calendar
import datetime
import hashlib
import json
import os
import urllib.parse

import boto3

REGION = "ap-southeast-1"

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


def verify_cmv(params, hash_key, hash_iv) -> bool:
    return params.get("CheckMacValue", "").upper() == gen_cmv(params, hash_key, hash_iv)


def add_one_month(dt):
    y, m = dt.year, dt.month + 1
    if m > 12:
        y, m = y + 1, 1
    last_day = calendar.monthrange(y, m)[1]
    return dt.replace(year=y, month=m, day=min(dt.day, last_day))


def _text(body, status=200):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/plain; charset=utf-8"},
        "body": body,
    }


def _parse_form(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return {
        k: v[0]
        for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()
    }


def handler(event, context):
    try:
        params = _parse_form(event)
        cfg = _get_ecpay()

        if not verify_cmv(params, cfg["hash_key"], cfg["hash_iv"]):
            print("CMV mismatch", params.get("MerchantTradeNo"))
            return _text("0|CheckMacValueInvalid", 400)

        if params.get("MerchantID") != cfg["merchant_id"]:
            print("MerchantID mismatch", params.get("MerchantID"))
            return _text("0|MerchantIDInvalid", 400)

        merchant_trade_no = params.get("MerchantTradeNo", "")
        email = params.get("CustomField1", "")
        route = params.get("CustomField2", "")

        if params.get("SimulatePaid") == "1":
            print("SimulatePaid ack (renewal, not extending)", merchant_trade_no)
            return _text("1|OK")

        if not email or not route:
            print("missing CustomField1/2", merchant_trade_no)
            return _text("1|OK")

        if params.get("RtnCode") == "1":
            now = datetime.datetime.now(datetime.timezone.utc)
            period_end = add_one_month(now)
            ddb.update_item(
                Key={"email": email, "route": route},
                UpdateExpression=(
                    "SET subscription_status = :active, current_period_end = :end, "
                    "current_period_end_date = :end_date, updated_at = :now"
                ),
                ExpressionAttributeValues={
                    ":active": "active",
                    ":end": period_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    ":end_date": period_end.strftime("%Y-%m-%d"),
                    ":now": now.isoformat(),
                },
            )
            print(
                "renewal ok, extended",
                email,
                route,
                "TotalSuccessTimes=" + params.get("TotalSuccessTimes", "?"),
            )
        else:
            # A single failed renewal does NOT expire the row — ECPay auto-retries
            # and only terminates the series after 6 consecutive failures.
            print(
                "renewal failed (not expiring — ECPay auto-retries)",
                email,
                route,
                params.get("RtnMsg"),
            )

        return _text("1|OK")
    except Exception as e:
        print("ERROR", repr(e))
        return _text("1|OK")
