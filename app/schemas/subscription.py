from datetime import datetime

from pydantic import BaseModel


class SubscriptionCreate(BaseModel):
    plan_name: str
    employee_limit: int
    branch_limit: int
    amount: float
    currency: str = "INR"
    start_date: datetime
    end_date: datetime
    status: str = "active"
    payment_reference: str | None = None


class SubscriptionUpdate(BaseModel):
    plan_name: str | None = None
    employee_limit: int | None = None
    branch_limit: int | None = None
    amount: float | None = None
    end_date: datetime | None = None
    status: str | None = None
    payment_reference: str | None = None
