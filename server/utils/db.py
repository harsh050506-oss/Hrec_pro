from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError
from .config import get_mongo_uri

_client = None
db = None


class DbUnavailable(Exception):
    pass


def init_db():
    global _client, db

    if db is not None:
        return db

    uri = get_mongo_uri()
    try:
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
    except (ConfigurationError, ServerSelectionTimeoutError) as e:
        raise DbUnavailable(
            "MongoDB is not reachable. Set HREC_MONGODB_URI to your Atlas connection string."
        ) from e

    db_name = uri.rsplit("/", 1)[-1].split("?")[0] or "hrec_db"
    db = _client[db_name]

    _ensure_indexes()
    return db


def _ensure_indexes():
    global db
    if db is None:
        return

    try:
        db.users.create_index("email", unique=True)
        db.jobs.create_index([("title", "text"), ("description", "text"), ("skills", "text")])
        db.applications.create_index([("job_id", 1), ("candidate_id", 1)], unique=True)
        db.resumes.create_index([("candidate_id", 1), ("job_id", 1)])
        db.tasks.create_index([("employee_id", 1), ("status", 1)])
    except Exception as e:
        print("DEBUG index creation warning:", repr(e))