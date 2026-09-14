import os
import json
import datetime
import urllib.request
import urllib.parse
from decimal import Decimal

import boto3

REGION = "ap-southeast-1"
QUEUE_URL = "https://sqs.ap-southeast-1.amazonaws.com/656559337546/flight-fare-queue"
UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"

_secrets = boto3.client("secretsmanager", region_name=REGION)
_sqs = boto3.client("sqs", region_name=REGION)
_subs = boto3.resource("dynamodb", region_name=REGION).Table("subscriptions")

_token_cache = None


def _get_token():
    global _token_cache
    if _token_cache is None:
        raw = _secrets.get_secret_value(SecretId="flight/travelpayouts")["SecretString"]
        _token_cache = json.loads(raw)["token"]
    return _token_cache


def _next_month():
    now = datetime.datetime.now(datetime.timezone.utc)
    year, month = now.year, now.month + 1
    if month > 12:
        year, month = year + 1, 1
    return f"{year:04d}-{month:02d}"


def fetch_cheapest(origin, destination, month, token, currency):
    q = urllib.parse.urlencode(
        {
            "origin": origin,
            "destination": destination,
            "depart_date": month,
            "currency": currency,
            "token": token,
        }
    )
    req = urllib.request.Request(
        f"https://api.travelpayouts.com/v1/prices/cheap?{q}",
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
    except Exception as e:
        print("fetch_cheapest error", currency, repr(e))
        return None
    if not body.get("success") or not body.get("data"):
        return None
    offers = body["data"].get(destination, {})
    if not offers:
        return None
    best = min(offers.values(), key=lambda o: o["price"])
    return {
        "price": best["price"],
        "currency": currency.upper(),
        "airline": best.get("airline"),
        "depart_date": best.get("departure_at"),
        "return_date": best.get("return_at"),
    }


def _is_eligible(item, now_iso):
    """Grace-aware paywall gate: active subscribers always qualify; a cancelled
    subscriber keeps getting alerts through current_period_end (string-compared —
    every writer uses the same fixed %Y-%m-%dT%H:%M:%SZ format). Rows with no
    subscription_status (pre-M2) or pending_payment/expired never qualify."""
    status = item.get("subscription_status")
    if status == "active":
        return True
    if status == "cancelled":
        end = item.get("current_period_end")
        if end and end >= now_iso:
            return True
        if end:
            _subs.update_item(
                Key={"email": item["email"], "route": item["route"]},
                UpdateExpression="SET subscription_status = :expired",
                ExpressionAttributeValues={":expired": "expired"},
            )
            print("lazily expired", item["email"], item["route"])
        return False
    return False


def handler(event, context):
    origin = event["origin"]
    destination = event["destination"]
    route = event["route"]
    token = _get_token()
    month = _next_month()

    tw = fetch_cheapest(origin, destination, month, token, "twd")
    if not tw:
        print("no TWD fare for", route, "(empty/429) - skipping")
        return {"ok": True, "route": route, "matched": 0}

    us = fetch_cheapest(origin, destination, month, token, "usd")

    result = _subs.scan(
        FilterExpression="#r = :r",
        ExpressionAttributeNames={"#r": "route"},
        ExpressionAttributeValues={":r": route},
    )
    items = result.get("Items", [])
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    matched = 0
    for it in items:
        tp = it.get("target_price")
        if tp is None:
            continue
        if not _is_eligible(it, now_iso):
            continue
        if Decimal(str(tp)) >= Decimal(str(tw["price"])):
            body = {
                "email": it["email"],
                "route": route,
                "plan_name": it.get("plan_name"),
                "target_price": int(tp),
                "cheapest": {
                    "price": tw["price"],
                    "currency": "TWD",
                    "airline": tw["airline"],
                    "depart_date": tw["depart_date"],
                    "return_date": tw["return_date"],
                },
            }
            if us:
                body["cheapest_usd"] = {
                    "price": us["price"],
                    "currency": "USD",
                    "airline": us["airline"],
                    "depart_date": us["depart_date"],
                    "return_date": us["return_date"],
                }
            _sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(body))
            matched += 1

    print(route, tw["price"], "TWD -", matched, "matched")
    return {"ok": True, "route": route, "matched": matched}
