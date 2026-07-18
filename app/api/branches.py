from app.api.crud import crud_router
from app.schemas.branch import BranchCreate, BranchUpdate
from app.services.catalog import BranchService

router = crud_router(BranchService(), BranchCreate, BranchUpdate, "branches")
