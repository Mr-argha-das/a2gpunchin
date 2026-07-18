import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.api.crud import crud_router
from app.core.dependencies import require_permissions
from app.models.employee import Employee
from app.models.employee_document import EmployeeDocument
from app.repositories.base import BaseRepository
from app.schemas.employee import EmployeeFaceEnroll
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.services.access_control import ACCESS_LEVEL_LABELS, normalize_access_level
from app.services.catalog import EmployeeService
from app.utils.serializers import document_to_dict

service = EmployeeService()
DOCUMENT_ROOT = Path("uploads/employee_documents")


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return name.strip("._") or "document"


def _document_row(document: EmployeeDocument) -> dict:
    return {
        "id": str(document.id),
        "document_name": document.document_name,
        "original_filename": document.original_filename,
        "content_type": document.content_type or "-",
        "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else document.created_at.isoformat(),
        "download_url": f"/api/employees/{document.employee_id.id}/documents/{document.id}/download",
    }


def _employee_row(employee: Employee) -> dict:
    branch = employee.branch_id
    shift = employee.shift_id
    department = employee.department_id
    branch_label = f"{branch.branch_name} ({branch.branch_code})" if branch else "-"
    shift_label = f"{shift.shift_name} ({shift.start_time}-{shift.end_time})" if shift else "-"
    department_label = f"{department.department_name} ({department.department_code})" if department else "-"
    access_label = "No Access"
    if employee.user_id:
        role_label = ACCESS_LEVEL_LABELS.get(normalize_access_level(getattr(employee.user_id, "access_level", None)), "Employee Self")
        modules = getattr(employee.user_id, "module_access", None) or getattr(employee, "module_access", None) or []
        module_label = ", ".join(module.replace("_", " ").title() for module in modules) if modules else "Default Modules"
        access_label = f"{role_label} / {module_label}"
    return {
        "id": str(employee.id),
        "employee_code": employee.employee_code,
        "prefix": employee.prefix or "-",
        "staff_role": (employee.staff_role or "-").replace("_", " ").title(),
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "father_name": employee.father_name or "-",
        "mother_name": employee.mother_name or "-",
        "email": employee.email,
        "office_email": employee.office_email or "-",
        "phone": employee.phone or "-",
        "emergency_contact_number": employee.emergency_contact_number or "-",
        "gender": (employee.gender or "-").replace("_", " ").title(),
        "date_of_birth": employee.date_of_birth.strftime("%d %b %Y") if employee.date_of_birth else "-",
        "joining_date": employee.joining_date.strftime("%d %b %Y") if employee.joining_date else "-",
        "marital_status": (employee.marital_status or "-").title(),
        "designation": employee.designation or "-",
        "department": department_label,
        "branch": branch_label,
        "shift": shift_label,
        "current_address": employee.current_address or "-",
        "permanent_address": employee.permanent_address or "-",
        "qualification": employee.qualification or "-",
        "work_experience": employee.work_experience or "-",
        "note": employee.note or "-",
        "aadhar_number": employee.aadhar_number or "-",
        "pan_number": employee.pan_number or "-",
        "bank_name": employee.bank_name or "-",
        "account_number": employee.account_number or "-",
        "ifsc_code": employee.ifsc_code or "-",
        "face": "Enrolled" if employee.face_enrolled else "Not Enrolled",
        "access": access_label,
        "status": employee.status.title() if employee.status else "-",
    }


router = crud_router(service, EmployeeCreate, EmployeeUpdate, "employees", list_serializer=_employee_row)


@router.post("/{employee_id}/face")
def enroll_face(employee_id: str, payload: EmployeeFaceEnroll, _=Depends(require_permissions("employees:update"))):
    employee = BaseRepository(Employee).get(employee_id)
    employee.face_embedding = payload.face_embedding
    employee.face_enrolled = True
    employee.save()
    return document_to_dict(employee)


@router.get("/{employee_id}/documents")
def list_employee_documents(employee_id: str, _=Depends(require_permissions("employees:read"))):
    employee = BaseRepository(Employee).get(employee_id)
    documents = EmployeeDocument.objects.visible().filter(employee_id=employee).order_by("-uploaded_at", "-created_at")
    return {"items": [_document_row(document) for document in documents], "total": documents.count()}


@router.post("/{employee_id}/documents", status_code=status.HTTP_201_CREATED)
def upload_employee_document(
    employee_id: str,
    document_name: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(require_permissions("employees:update")),
):
    employee = BaseRepository(Employee).get(employee_id)
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A file is required.")

    employee_dir = DOCUMENT_ROOT / employee_id
    employee_dir.mkdir(parents=True, exist_ok=True)
    original_filename = _safe_filename(file.filename)
    stored_filename = f"{uuid4().hex}_{original_filename}"
    file_path = employee_dir / stored_filename
    with file_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    document = EmployeeDocument(
        tenant_id=employee.tenant_id,
        company_id=employee.company_id,
        employee_id=employee,
        document_name=document_name.strip(),
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=str(file_path),
        content_type=file.content_type,
        uploaded_at=datetime.now(timezone.utc),
        created_by=str(user.id),
    ).save()
    return _document_row(document)


@router.get("/{employee_id}/documents/{document_id}/download")
def download_employee_document(employee_id: str, document_id: str, _=Depends(require_permissions("employees:read"))):
    employee = BaseRepository(Employee).get(employee_id)
    document = EmployeeDocument.objects.visible().filter(id=document_id, employee_id=employee).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    path = Path(document.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded file is missing")
    return FileResponse(path, media_type=document.content_type or "application/octet-stream", filename=document.original_filename)
