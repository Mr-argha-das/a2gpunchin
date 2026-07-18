from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MongoModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True, json_encoders={})

    id: str | None = None


class Page(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class AuditFields(BaseModel):
    tenant_id: str | None = None
    company_id: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_active: bool = True


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    sort: str = "-created_at"
