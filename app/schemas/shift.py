from pydantic import BaseModel, Field


class ShiftCreate(BaseModel):
    shift_name: str
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    grace_time: int = Field(default=0, ge=0)
    late_after: int = Field(default=0, ge=0)
    half_day_after: int = Field(default=0, ge=0)
    after_half_day_after: int = Field(default=0, ge=0)
    early_logout_before: int = Field(default=0, ge=0)
    is_night_shift: bool = False


class ShiftUpdate(BaseModel):
    shift_name: str | None = None
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    grace_time: int | None = Field(default=None, ge=0)
    late_after: int | None = Field(default=None, ge=0)
    half_day_after: int | None = Field(default=None, ge=0)
    after_half_day_after: int | None = Field(default=None, ge=0)
    early_logout_before: int | None = Field(default=None, ge=0)
    is_night_shift: bool | None = None
