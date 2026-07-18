from fastapi import HTTPException, status

from app.models.leave import Leave
from app.repositories.base import BaseRepository
from app.services.base import BaseService


class LeaveService(BaseService):
    search_fields = ["leave_type", "status", "reason"]

    def __init__(self):
        super().__init__(BaseRepository(Leave))

    def apply(self, data: dict) -> Leave:
        total_days = (data["end_date"] - data["start_date"]).days + 1
        if total_days <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date must be after start date")
        data["total_days"] = total_days
        return self.create(data)

    def decide(self, leave_id: str, status_value: str, remarks: str | None) -> Leave:
        leave = self.repository.get(leave_id)
        if status_value not in {"pending_hr", "approved", "rejected"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid leave status")
        if leave.status == "pending_manager":
            leave.manager_remarks = remarks
        else:
            leave.hr_remarks = remarks
        leave.status = status_value
        leave.save()
        return leave
