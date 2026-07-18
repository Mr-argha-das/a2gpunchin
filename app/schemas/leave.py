from datetime import date

from pydantic import BaseModel


class LeaveCreate(BaseModel):
    employee_id: str
    leave_type: str
    start_date: date
    end_date: date
    reason: str | None = None


class LeaveDecision(BaseModel):
    status: str
    remarks: str | None = None
