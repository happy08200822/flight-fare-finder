import os
import json

import boto3

REGION = "ap-southeast-1"
_s3 = boto3.client("s3", region_name=REGION)
_lambda = boto3.client("lambda", region_name=REGION)


def handler(event, context):
    bucket = os.environ["CONFIG_BUCKET"]
    obj = _s3.get_object(Bucket=bucket, Key="flight-routes.json")
    routes = json.loads(obj["Body"].read())

    invoked = []
    for r in routes:
        payload = {
            "origin": r["origin"],
            "destination": r["destination"],
            "route": f"{r['origin']}-{r['destination']}",
        }
        _lambda.invoke(
            FunctionName="flight-parser",
            InvocationType="Event",
            Payload=json.dumps(payload).encode(),
        )
        invoked.append(payload["route"])

    print("dispatched", invoked)
    return {"ok": True, "dispatched": invoked}
