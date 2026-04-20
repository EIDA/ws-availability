import sentry_sdk

from config import Config


def before_send(event, hint):
    """
    Scrub sensitive data from Sentry events before sending.
    This prevents passwords, API keys, and other secrets from being exposed.
    """
    sensitive_keys = {
        "password", "passwd", "pwd", "secret", "api_key", "apikey",
        "token", "auth", "authorization", "credentials", "private_key",
        "access_token", "refresh_token", "session", "cookie"
    }

    def scrub_dict(data):
        """Recursively scrub sensitive data from dictionaries."""
        if not isinstance(data, dict):
            return

        for key in list(data.keys()):
            key_lower = str(key).lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                data[key] = "[Filtered]"
            elif isinstance(data[key], dict):
                scrub_dict(data[key])
            elif isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict):
                        scrub_dict(item)

    # Scrub request data (including IP headers)
    if "request" in event:
        scrub_dict(event["request"])
        if "headers" in event["request"]:
            headers = event["request"]["headers"]
            for ip_header in ["X-Forwarded-For", "X-Real-Ip", "True-Client-Ip", "Cf-Connecting-Ip"]:
                if ip_header in headers:
                    headers[ip_header] = "[Filtered]"
                if ip_header.lower() in headers:
                    headers[ip_header.lower()] = "[Filtered]"

        if "env" in event["request"] and "REMOTE_ADDR" in event["request"]["env"]:
            event["request"]["env"]["REMOTE_ADDR"] = "[Filtered]"

    # Scrub extra context
    if "extra" in event:
        scrub_dict(event["extra"])

    # Aggressively clear user IP
    if "user" not in event or event["user"] is None:
        event["user"] = {}

    event["user"]["ip_address"] = "0.0.0.0"
    scrub_dict(event["user"])

    # Scrub breadcrumbs
    if "breadcrumbs" in event:
        for breadcrumb in event["breadcrumbs"].get("values", []):
            scrub_dict(breadcrumb)

    # Scrub local variables from stack traces
    if "exception" in event:
        for exception in event["exception"].get("values", []):
            if "stacktrace" in exception:
                for frame in exception["stacktrace"].get("frames", []):
                    if "vars" in frame:
                        scrub_dict(frame["vars"])

    return event


def init_sentry():
    """Initialize Sentry SDK if SENTRY_DSN is configured."""
    if Config.SENTRY_DSN:
        sentry_sdk.init(
            dsn=Config.SENTRY_DSN,
            traces_sample_rate=Config.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,
            before_send=before_send,
        )
