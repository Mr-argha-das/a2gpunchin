from mongoengine import connect

from app.core.config import settings


def connect_database() -> None:
    connect(host=settings.mongodb_uri, alias="default", uuidRepresentation="standard")
