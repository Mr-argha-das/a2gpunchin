from mongoengine import Document
from bson import ObjectId


def serialize_value(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}
    return value


def document_to_dict(document: Document) -> dict:
    data = document.to_mongo().to_dict()
    data["id"] = str(data.pop("_id"))
    for key, value in list(data.items()):
        if hasattr(value, "binary"):
            data[key] = str(value)
        else:
            data[key] = serialize_value(value)
    return data


def documents_to_dicts(documents: list[Document]) -> list[dict]:
    return [document_to_dict(document) for document in documents]
