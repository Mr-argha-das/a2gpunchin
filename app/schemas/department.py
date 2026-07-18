from pydantic import BaseModel


class DepartmentCreate(BaseModel):
    department_name: str
    department_code: str
    description: str | None = None


class DepartmentUpdate(BaseModel):
    department_name: str | None = None
    description: str | None = None
