from app.api.crud import crud_router
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from app.services.catalog import SubscriptionService

router = crud_router(SubscriptionService(), SubscriptionCreate, SubscriptionUpdate, "subscriptions")
