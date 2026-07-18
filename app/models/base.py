from datetime import datetime, timezone

from mongoengine import BooleanField, DateTimeField, Document, QuerySet, StringField

from app.core.tenant import current_company_id, current_is_super_admin, current_tenant_id, current_user_id


class TenantQuerySet(QuerySet):
    def visible(self):
        if current_is_super_admin.get():
            return self.filter(is_active=True)
        tenant_id = current_tenant_id.get()
        company_id = current_company_id.get()
        query = self.filter(is_active=True)
        if tenant_id and "tenant_id" in self._document._fields:
            query = query.filter(tenant_id=tenant_id)
        if company_id and "company_id" in self._document._fields and self._document.__name__ not in {"Tenant", "Company"}:
            query = query.filter(company_id=company_id)
        return query


class BaseDocument(Document):
    meta = {"abstract": True, "queryset_class": TenantQuerySet}

    tenant_id = StringField(required=True)
    company_id = StringField(required=False, null=True)
    created_by = StringField(required=False, null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    is_active = BooleanField(default=True)

    def clean(self):
        if not self.tenant_id:
            self.tenant_id = current_tenant_id.get()
        if not self.company_id:
            self.company_id = current_company_id.get()
        if not self.created_by:
            self.created_by = current_user_id.get()
        self.updated_at = datetime.now(timezone.utc)

    def soft_delete(self):
        self.is_active = False
        self.save()
