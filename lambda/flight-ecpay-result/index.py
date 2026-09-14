import base64
import os
import urllib.parse

SITE_URL = os.environ["SITE_URL"]


def _parse_form(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return {
        k: v[0]
        for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()
    }


def handler(event, context):
    # ECPay delivers OrderResultURL as a browser POST — a static SPA would 405 on
    # that. This tiny Lambda's only job is to turn the POST into a redirect. It
    # does no auth/activation work; ReturnURL is the source of truth for that.
    params = _parse_form(event)
    rtn_code = params.get("RtnCode", "")
    suffix = "purchase=success" if rtn_code == "1" else "purchase=failed"
    return {
        "statusCode": 302,
        "headers": {"Location": f"{SITE_URL}/app?{suffix}"},
    }
