from bson import ObjectId


def oid(value):
    if isinstance(value, ObjectId):
        return str(value)
    return str(value)


def doc_to_json(doc: dict) -> dict:
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = oid(v)
        elif isinstance(v, ObjectId):
            out[k] = oid(v)
        else:
            out[k] = v
    return out

