from app.api.crud import crud_router
from app.schemas.shift import ShiftCreate, ShiftUpdate
from app.services.catalog import ShiftService

router = crud_router(ShiftService(), ShiftCreate, ShiftUpdate, "shifts")
