from bson import ObjectId

from utils.db import init_db


def hiring_funnel_counts():
    db = init_db()
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    rows = list(db.applications.aggregate(pipeline))
    out = {"Pending": 0, "Accepted": 0, "Rejected": 0}
    for r in rows:
        out[r["_id"]] = r["count"]
    return out


def performance_series(limit=30):
    db = init_db()
    items = list(db.performance.find({}).sort("updated_at", -1).limit(int(limit)))
    # return latest first; UI can reverse
    series = []
    for p in items:
        series.append(
            {
                "employee_id": str(p["employee_id"]),
                "score": int(p.get("score", 0)),
                "updated_at": p.get("updated_at"),
            }
        )
    return series

