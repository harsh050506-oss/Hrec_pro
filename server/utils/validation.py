from datetime import datetime


def require_fields(data: dict, fields: list[str]):
    missing = [f for f in fields if data.get(f) in (None, "", [])]
    if missing:
        return f"Missing fields: {', '.join(missing)}"
    return None


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    # allow comma-separated strings
    return [x.strip() for x in str(value).split(",") if x.strip()]


def now_utc():
    return datetime.utcnow()

