import boto3
import json
from decimal import Decimal
from boto3.dynamodb.conditions import Key

ddb = boto3.resource("dynamodb").Table("subscriptions")


def _default(o):
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    raise TypeError


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, default=_default),
    }


def handler(event, context):
    try:
        params = event.get("queryStringParameters") or {}
        email = (params.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return _response(400, {"error": "invalid email"})

        result = ddb.query(KeyConditionExpression=Key("email").eq(email))
        return _response(200, {"items": result.get("Items", [])})
    except Exception as e:
        print("ERROR", repr(e))
        return _response(500, {"error": "internal error"})
