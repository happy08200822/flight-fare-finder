import boto3
import json
import datetime
from decimal import Decimal, InvalidOperation

PLANS = {
    "tokyo": {"origin": "TPE", "destination": "TYO"},
    "seoul": {"origin": "TPE", "destination": "SEL"},
}

ddb = boto3.resource("dynamodb").Table("subscriptions")


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def handler(event, context):
    try:
        raw = event.get("body", event)
        body = json.loads(raw) if isinstance(raw, str) else raw

        email = (body.get("email") or "").strip().lower()
        plan_name = body.get("plan_name")
        target_price = body.get("target_price")

        if not email or "@" not in email:
            return _response(400, {"error": "invalid email"})
        if plan_name not in PLANS:
            return _response(400, {"error": "invalid plan_name"})
        try:
            target_price_dec = Decimal(str(target_price))
        except (InvalidOperation, TypeError):
            return _response(400, {"error": "invalid target_price"})
        if target_price_dec <= 0:
            return _response(400, {"error": "target_price must be positive"})

        plan = PLANS[plan_name]
        origin, destination = plan["origin"], plan["destination"]
        route = f"{origin}-{destination}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        existing = ddb.get_item(Key={"email": email, "route": route}).get("Item")
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
                "created_at": created_at,
                "updated_at": now,
            }
        )

        return _response(200, {"ok": True, "route": route})
    except Exception as e:
        print("ERROR", repr(e))
        return _response(500, {"error": "internal error"})
