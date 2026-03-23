import os

def get_mongo_uri():
    return os.getenv(
        "HREC_MONGODB_URI",
        "mongodb+srv://<USERNAME>:<PASSWORD>@hrec-cluster.mongodb.net/hrec_db",
    )

def get_openai_key():
    return os.getenv("OPENAI_API_KEY", "").strip()

def get_openai_model():
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()