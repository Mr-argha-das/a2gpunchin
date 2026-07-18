from fastapi import APIRouter, Depends, Query

from app.core.dependencies import require_permissions
from app.models.user import User
from app.schemas.leave import LeaveCreate, LeaveDecision
from app.services.access_control import scoped_employees_for_user
from app.services.leave import LeaveService
from app.utils.serializers import document_to_dict, documents_to_dicts

router = APIRouter()
service = LeaveService()


@router.get("")
def list_leaves(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str | None = None, user: User = Depends(require_permissions("leaves:read"))):
    filters = {}
    scoped_employees = scoped_employees_for_user(user)
    if scoped_employees is not None:
        filters["employee_id__in"] = scoped_employees
    items, total = service.list(page=page, page_size=page_size, search=search, **filters)
    return {"items": documents_to_dicts(items), "total": total, "page": page, "page_size": page_size}


@router.post("")
def apply_leave(payload: LeaveCreate, user: User = Depends(require_permissions("leaves:create"))):
    data = payload.model_dump(exclude_none=True)
    scoped_employees = scoped_employees_for_user(user)
    if scoped_employees is not None:
        scoped_ids = {str(employee.id) for employee in scoped_employees}
        if data["employee_id"] not in scoped_ids:
            data["employee_id"] = next(iter(scoped_ids), data["employee_id"])
    return document_to_dict(service.apply(data))


@router.post("/{leave_id}/decision")
def decide_leave(leave_id: str, payload: LeaveDecision, _=Depends(require_permissions("leaves:approve"))):
    return document_to_dict(service.decide(leave_id, payload.status, payload.remarks))
