from app.api.crud import crud_router
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.catalog import CompanyService

router = crud_router(CompanyService(), CompanyCreate, CompanyUpdate, "companies")
