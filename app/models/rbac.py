from mongoengine import ListField, ReferenceField, StringField

from app.models.base import BaseDocument


class Permission(BaseDocument):
    meta = {"collection": "permissions", "indexes": ["code", "tenant_id"]}

    code = StringField(required=True, unique=True)
    name = StringField(required=True)
    module = StringField(required=True)


class Role(BaseDocument):
    meta = {"collection": "roles", "indexes": ["tenant_id", "company_id", "name"]}

    name = StringField(required=True)
    slug = StringField(required=True)
    permissions = ListField(ReferenceField(Permission))
