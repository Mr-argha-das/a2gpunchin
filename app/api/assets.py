from fastapi import Depends, Query, status

from app.api.crud import crud_router
from app.core.dependencies import require_permissions
from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetUpdate
from app.services.catalog import AssetService

service = AssetService()


def _asset_row(asset: Asset) -> dict:
    employee = asset.employee_id
    employee_label = "-"
    department_label = "-"
    phone_label = "-"
    if employee:
        employee_label = f"{employee.employee_code} - {employee.first_name} {employee.last_name}"
        department = employee.department_id
        department_label = f"{department.department_name} ({department.department_code})" if department else "-"
        phone_label = employee.phone or "-"
    return {
        "id": str(asset.id),
        "asset_id": asset.asset_id,
        "asset_type": (asset.asset_type or "-").replace("_", " ").title(),
        "asset_name": asset.asset_name,
        "brand_model": asset.brand_model or "-",
        "serial_number": asset.serial_number or "-",
        "sim_number": asset.sim_number or "-",
        "employee": employee_label,
        "employee_phone": phone_label,
        "department": department_label,
        "assigned_on": asset.assigned_on.strftime("%d %b %Y") if asset.assigned_on else "-",
        "returned_on": asset.returned_on.strftime("%d %b %Y") if asset.returned_on else "-",
        "status": (asset.status or "-").title(),
        "condition": asset.condition or "-",
        "note": asset.note or "-",
    }


router = crud_router(service, AssetCreate, AssetUpdate, "assets", list_serializer=_asset_row, include_list=False)


@router.get("")
def list_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    sort: str = "-created_at",
    employee_id: str | None = None,
    asset_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    _=Depends(require_permissions("assets:read")),
):
    filters = {
        "employee_id": employee_id,
        "asset_type": asset_type,
        "status": status_filter,
    }
    items, total = service.list(page=page, page_size=page_size, search=search, sort=sort, **filters)
    return {"items": [_asset_row(item) for item in items], "total": total, "page": page, "page_size": page_size}
