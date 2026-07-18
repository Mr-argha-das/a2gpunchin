from typing import Any, Generic, TypeVar

from fastapi import HTTPException, status
from mongoengine import Document
from mongoengine.queryset.visitor import Q

ModelT = TypeVar("ModelT", bound=Document)


class BaseRepository(Generic[ModelT]):
    def __init__(self, model: type[ModelT]):
        self.model = model

    def list(
        self,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        search_fields: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "-created_at",
        select_related_depth: int | None = None,
    ) -> tuple[list[ModelT], int]:
        query = self.model.objects.visible()
        if filters:
            query = query.filter(**{key: value for key, value in filters.items() if value not in (None, "")})
        if search and search_fields:
            search_query = Q()
            for field in search_fields:
                search_query |= Q(**{f"{field}__icontains": search})
            query = query.filter(search_query)
        total = query.count()
        items = query.order_by(sort).skip((page - 1) * page_size).limit(page_size)
        if select_related_depth:
            items = items.select_related(max_depth=select_related_depth)
        return list(items), total

    def get(self, object_id: str) -> ModelT:
        item = self.model.objects.visible().filter(id=object_id).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{self.model.__name__} not found")
        return item

    def create(self, data: dict[str, Any]) -> ModelT:
        item = self.model(**data)
        item.save()
        return item

    def update(self, object_id: str, data: dict[str, Any]) -> ModelT:
        item = self.get(object_id)
        for key, value in data.items():
            if value is not None:
                setattr(item, key, value)
        item.save()
        return item

    def delete(self, object_id: str) -> None:
        item = self.get(object_id)
        item.soft_delete()
