from app.api.crud import crud_router
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services.catalog import DepartmentService

router = crud_router(DepartmentService(), DepartmentCreate, DepartmentUpdate, "departments")
