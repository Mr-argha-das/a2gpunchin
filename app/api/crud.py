from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.core.dependencies import require_permissions
from app.services.base import BaseService
from app.utils.serializers import document_to_dict, documents_to_dicts


def crud_router(
    service: BaseService,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    permission_prefix: str,
    list_serializer: Callable[[Any], dict] | None = None,
    include_list: bool = True,
) -> APIRouter:
    router = APIRouter()

    if include_list:
        @router.get("")
        def list_items(
            page: int = Query(1, ge=1),
            page_size: int = Query(20, ge=1, le=100),
            search: str | None = None,
            sort: str = "-created_at",
            branch_id: str | None = None,
            department_id: str | None = None,
            status: str | None = None,
            _=Depends(require_permissions(f"{permission_prefix}:read")),
        ):
            filters = {}
            if permission_prefix == "employees" and branch_id:
                filters["branch_id"] = branch_id
            if permission_prefix == "employees" and department_id:
                filters["department_id"] = department_id
            if permission_prefix == "employees" and status:
                filters["status"] = status
            if permission_prefix == "employees":
                filters["current_user"] = _
            items, total = service.list(page=page, page_size=page_size, search=search, sort=sort, **filters)
            serialized = [list_serializer(item) for item in items] if list_serializer else documents_to_dicts(items)
            return {"items": serialized, "total": total, "page": page, "page_size": page_size}

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_item(payload: create_schema, user=Depends(require_permissions(f"{permission_prefix}:create"))):  # type: ignore[valid-type]
        data = payload.model_dump(exclude_none=True)
        if permission_prefix != "companies":
            data.setdefault("tenant_id", user.tenant_id)
            data.setdefault("company_id", user.company_id)
            data.setdefault("created_by", str(user.id))
        return document_to_dict(service.create(data))

    @router.get("/{item_id}")
    def detail(item_id: str, _=Depends(require_permissions(f"{permission_prefix}:read"))):
        return document_to_dict(service.get(item_id))

    @router.put("/{item_id}")
    def update_item(item_id: str, payload: update_schema, _=Depends(require_permissions(f"{permission_prefix}:update"))):  # type: ignore[valid-type]
        return document_to_dict(service.update(item_id, payload.model_dump(exclude_none=True)))

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_item(item_id: str, _=Depends(require_permissions(f"{permission_prefix}:delete"))):
        service.delete(item_id)

    return router
